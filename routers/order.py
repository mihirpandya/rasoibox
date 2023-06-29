import json
import logging
import random
import string
from datetime import datetime
from functools import reduce
from typing import List, Dict, Any, Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

import models.orders
from api.orders import Order, CartItem, PricedCartItem
from config import Settings
from dependencies.customers import get_current_customer
from dependencies.database import get_db
from dependencies.stripe_utils import create_checkout_session, find_promo_code_id
from emails.base import send_email, ReceiptEmail
from models.customers import Customer
from models.orders import Cart, Coupon, PaymentStatusEnum
from models.recipes import Recipe, RecipePrice
from models.signups import VerifiedSignUp, UnverifiedSignUp
from routers.signup import smtp_server, jinjaEnv

logger = logging.getLogger("rasoibox")

router = APIRouter(
    prefix="/api/order",
    tags=["order"]
)

settings: Settings = Settings()


def generate_order_id() -> str:
    res = ''.join(random.choices(string.digits, k=8))
    return res.lower()


def send_receipt_email_best_effort(email: str, first_name: str, order_dict: Dict[str, Any]):
    # send email with password reset link
    url_base: str = settings.frontend_url_base[0:-1] if settings.frontend_url_base.endswith(
        "/") else settings.frontend_url_base
    recipes = order_dict["recipes"]
    line_items: List[Dict[str, Any]] = [
        {"name": x, "serving_size": recipes[x]["serving_size"], "price": recipes[x]["price"]} for x in recipes.keys()]
    sub_total: float = reduce(lambda d1, d2: d1 + d2, order_dict["order_breakdown"]["items"].values(), 0)
    coupons = order_dict["order_breakdown"]["coupons"]
    if len(coupons) == 0:
        coupon = {}
    else:
        coupon = coupons[0]

    receipt_email: ReceiptEmail = ReceiptEmail(
        url_base=url_base,
        first_name=first_name,
        line_items=line_items,
        coupon=coupon,
        total=order_dict["order_total_dollars"],
        sub_total=sub_total,
        shipping_address=order_dict["order_delivery_address"],
        order_id=order_dict["order_number"],
        to_email=email,
        from_email=settings.from_email
    )

    # send email best effort
    try:
        send_email(jinjaEnv, receipt_email, smtp_server, settings.email, settings.email_app_password)
    except Exception:
        logger.exception("Failed to send email.")


@router.post("/initiate_place_order")
async def initiate_place_order(order: Order, current_customer: Customer = Depends(get_current_customer),
                               db: Session = Depends(get_db)):
    verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.email == current_customer.email).first()
    if verified_sign_up is None:
        raise HTTPException(status_code=400, detail="User is not verified.")

    cart_items_by_recipe_id: Dict[int, Cart] = reduce(lambda d1, d2: {**d1, **d2},
                                                      [{x.recipe_id: x} for x in db.query(Cart).filter(
                                                          Cart.verification_code == verified_sign_up.verification_code)
                                                      .all()], {})

    coupons: List[Coupon] = db.query(Coupon).filter(Coupon.coupon_name.in_(order.coupons)).all()
    if len(coupons) is not len(order.coupons):
        raise HTTPException(status_code=400, detail="Invalid coupons.")

    recipes_serving_size_map: Dict[int, int] = {}
    recipe_prices_ordered: List[RecipePrice] = []

    for recipe_id in cart_items_by_recipe_id.keys():
        serving_size = cart_items_by_recipe_id[recipe_id].serving_size
        recipes_serving_size_map[recipe_id] = serving_size
        recipe_price: RecipePrice = db.query(RecipePrice).filter(
            and_(RecipePrice.recipe_id == recipe_id, RecipePrice.serving_size == serving_size)).first()
        if recipe_price is None:
            raise HTTPException(status_code=404, detail="Invalid recipe serving size combo")
        recipe_prices_ordered.append(recipe_price)

    order_total_dollars = reduce(lambda p1, p2: p1 + p2, [x.price for x in recipe_prices_ordered], 0)
    for coupon in coupons:
        if coupon.amount_off is not None and coupon.amount_off > 0:
            order_total_dollars = order_total_dollars - coupon.amount_off
        elif coupon.percent_off is not None and coupon.percent_off > 0:
            order_total_dollars = (1.0 - (coupon.percent_off / 100.0)) * order_total_dollars
    order_breakdown_dollars = reduce(lambda d1, d2: {**d1, **d2}, [{x.id: x.price} for x in recipe_prices_ordered], {})
    order_breakdown = {
        "items": order_breakdown_dollars,
        "coupons": [{"name": x.coupon_name, "amount_off": x.amount_off, "percent_off": x.percent_off} for x in coupons]
    }
    stripe_price_ids = [x.stripe_price_id for x in recipe_prices_ordered]
    user_facing_order_id = generate_order_id()
    order_date = datetime.now()

    db.add(models.orders.Order(
        user_facing_order_id=user_facing_order_id,
        order_date=order_date,
        recipes=json.dumps(recipes_serving_size_map),
        recipient_first_name=order.recipient_first_name,
        recipient_last_name=order.recipient_last_name,
        payment_status=PaymentStatusEnum.INITIATED,
        customer=current_customer.id,
        delivered=False,
        order_total_dollars=round(order_total_dollars, 2),
        order_breakdown_dollars=json.dumps(order_breakdown),
        delivery_address=jsonable_encoder(order.delivery_address),
        phone_number=order.phone_number,
        coupons=json.dumps([x.id for x in coupons])
    ))

    db.commit()

    try:
        checkout_session = create_checkout_session(stripe_price_ids,
                                                   settings.frontend_url_base + "success?orderId=" + user_facing_order_id,
                                                   settings.frontend_url_base + "cancel?orderId=" + user_facing_order_id,
                                                   user_facing_order_id, current_customer.email,
                                                   [x.coupon_name for x in coupons])
        logger.info("Successfully created checkout session {}".format(checkout_session))
        return JSONResponse(content=jsonable_encoder({"session_url": checkout_session.url}))
    except Exception:
        logger.exception("Failed to create checkout session.")
        db.query(models.orders.Order).filter(models.orders.Order.user_facing_order_id == user_facing_order_id) \
            .update({models.orders.Order.payment_status: PaymentStatusEnum.FAILED})
        db.commit()
        logger.info("Updated payment status")
        raise HTTPException(status_code=400, detail="Failed to create Stripe checkout session")


@router.post("/complete_place_order")
async def complete_place_order(order_id: str, current_customer: Customer = Depends(get_current_customer),
                               db: Session = Depends(get_db)):
    order: models.orders.Order = db.query(models.orders.Order).filter(
        models.orders.Order.user_facing_order_id == order_id).first()
    if order is None or order.customer != current_customer.id:
        raise HTTPException(status_code=404, detail="Unknown order")
    verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.email == current_customer.email).first()
    if verified_sign_up is None:
        raise HTTPException(status_code=400, detail="User is not verified.")

    if models.orders.Order.payment_status == PaymentStatusEnum.INITIATED:
        db.query(models.orders.Order).filter(models.orders.Order.user_facing_order_id == order_id).update(
            {"payment_status": PaymentStatusEnum.COMPLETED})
        db.query(Cart).filter(Cart.verification_code == verified_sign_up.verification_code).delete()
        db.commit()

        order: models.orders.Order = db.query(models.orders.Order).filter(
            models.orders.Order.user_facing_order_id == order_id).first()

        # send email
        result = to_order_dict(order, db)
        send_receipt_email_best_effort(current_customer.email, current_customer.first_name, result)

        return JSONResponse(content=jsonable_encoder(result))
    else:
        return JSONResponse(content=jsonable_encoder(to_order_dict(order, db)))


@router.post("/cancel_place_order")
async def cancel_place_order(order_id: str, current_customer: Customer = Depends(get_current_customer),
                             db: Session = Depends(get_db)):
    order = db.query(models.orders.Order).filter(models.orders.Order.user_facing_order_id == order_id).first()
    if order is None or order.customer != current_customer.id:
        raise HTTPException(status_code=404, detail="Unknown order")
    db.query(models.orders.Order).filter(models.orders.Order.user_facing_order_id == order_id).update(
        {"payment_status": PaymentStatusEnum.CANCELED})
    db.commit()


@router.get("/get_cart")
async def get_cart(verification_code: str, db: Session = Depends(get_db)):
    cart_items: List[Cart] = db.query(Cart).filter(Cart.verification_code == verification_code).all()
    cart_recipe_ids: List[str] = [x.recipe_id for x in cart_items]
    recipe_info: Dict[int, Dict[str, str]] = reduce(lambda d1, d2: {**d1, **d2},
                                                    [{x.id: {"name": x.name, "image_url": x.image_url}} for x in
                                                     db.query(Recipe).filter(
                                                         Recipe.id.in_(cart_recipe_ids))], {})
    result: List[PricedCartItem] = []
    for cart_item in cart_items:
        recipe_name = recipe_info[cart_item.recipe_id]["name"]
        recipe_image_url = recipe_info[cart_item.recipe_id]["image_url"]
        recipe_price: RecipePrice = db.query(RecipePrice).filter(and_(RecipePrice.recipe_id == cart_item.recipe_id,
                                                                      RecipePrice.serving_size == cart_item.serving_size)).first()
        if recipe_price is None:
            raise HTTPException(status_code=400,
                                detail="Could not find price {}".format(recipe_name))
        result.append(
            PricedCartItem(recipe_name=recipe_name, image_url=recipe_image_url, serving_size=recipe_price.serving_size,
                           price=recipe_price.price))

    return JSONResponse(content=jsonable_encoder(result))


@router.post("/update_cart")
async def update_cart(cart_item: CartItem, verification_code: str,
                      db: Session = Depends(get_db)):
    if not is_known_verification_code(verification_code, db):
        raise HTTPException(status_code=404, detail="Unknown user")

    recipe: Recipe = db.query(Recipe).filter(Recipe.name == cart_item.recipe_name).first()
    if recipe is None:
        raise HTTPException(status_code=404, detail="Unknown recipe {}".format(cart_item.recipe_name))
    existing_cart_item: Cart = db.query(Cart).filter(
        and_(Cart.recipe_id == recipe.id, Cart.verification_code == verification_code)).first()

    if existing_cart_item is None:
        if cart_item.serving_size > 0:
            # add new item
            db.add(Cart(verification_code=verification_code, recipe_id=recipe.id, serving_size=cart_item.serving_size))
    else:
        if cart_item.serving_size > 0:
            db.query(Cart).filter(
                and_(Cart.recipe_id == recipe.id, Cart.verification_code == verification_code)).update(
                {Cart.serving_size: cart_item.serving_size})
        else:
            db.delete(existing_cart_item)

    db.commit()


@router.get("/get_available_items")
async def get_available_items(db: Session = Depends(get_db)):
    recipe_prices: List[RecipePrice] = db.query(RecipePrice).all()
    recipe_ids: List[int] = list(set([x.recipe_id for x in recipe_prices]))
    recipes: Dict[int, Recipe] = reduce(lambda d1, d2: {**d1, **d2},
                                        [{x.id: x} for x in db.query(Recipe).filter(Recipe.id.in_(recipe_ids))], {})
    result = {}
    for recipe_price in recipe_prices:
        if recipe_price.recipe_id not in recipes:
            raise HTTPException(status_code=400, detail="Unknown recipe {}".format(recipe_price.recipe_id))
        if recipe_price.recipe_id in result:
            result[recipe_price.recipe_id]["serving_sizes"].append(recipe_price.serving_size)
            result[recipe_price.recipe_id]["prices"].append(recipe_price.price)
        else:
            recipe: Recipe = recipes[recipe_price.recipe_id]
            tags = recipe.tags if recipe.tags is not None else json.dumps([])
            result[recipe_price.recipe_id] = {
                "recipe_name": recipe.name,
                "description": recipe.description,
                "image_url": recipe.image_url,
                "serving_sizes": [recipe_price.serving_size],
                "prices": [recipe_price.price],
                "cook_time": recipe.cook_time_minutes,
                "prep_time": recipe.prep_time_minutes,
                "tags": json.loads(tags)
            }

    return JSONResponse(content=jsonable_encoder(result))


@router.get("/get_order")
async def get_order_from_order_id(order_id: str, current_customer: Customer = Depends(get_current_customer),
                                  db: Session = Depends(get_db)):
    order = db.query(models.orders.Order).filter(and_(models.orders.Order.user_facing_order_id == order_id,
                                                      models.orders.Order.customer == current_customer.id)).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Unknown order")

    return JSONResponse(content=jsonable_encoder(to_order_dict(order, db)))


@router.get("/get_order_history")
async def get_order_history(current_customer: Customer = Depends(get_current_customer),
                            db: Session = Depends(get_db)):
    orders: List[models.orders.Order] = db.query(models.orders.Order).filter(
        models.orders.Order.customer == current_customer.id).all()
    return JSONResponse(content=jsonable_encoder([to_order_dict(x, db) for x in orders]))


@router.get("/get_active_recipes")
async def get_active_recipes(current_customer: Customer = Depends(get_current_customer),
                             db: Session = Depends(get_db)):
    orders: List[models.orders.Order] = db.query(models.orders.Order).filter(and_(
        models.orders.Order.customer == current_customer.id,
        models.orders.Order.payment_status == PaymentStatusEnum.COMPLETED)).all()

    active_orders: List[Dict[str, Any]] = [to_order_dict(x, db) for x in orders if is_active_order(x)]
    return JSONResponse(content=jsonable_encoder(active_orders))


@router.get("/is_valid_coupon")
async def is_valid_coupon(coupon_code: str, current_customer: Customer = Depends(get_current_customer),
                          db: Session = Depends(get_db)):
    verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.email == current_customer.email).first()
    if verified_sign_up is None:
        raise HTTPException(status_code=404, detail="Unknown coupon")

    coupon: Coupon = db.query(Coupon).filter(and_(Coupon.coupon_name == coupon_code,
                                                  Coupon.redeemable_by_verification_code == verified_sign_up.verification_code)).first()

    if coupon is None:
        raise HTTPException(status_code=404, detail="Unknown coupon")

    now = datetime.now()
    if now > coupon.expires_on:
        raise HTTPException(status_code=400, detail="Expired coupon")

    promo_code = find_promo_code_id(coupon.coupon_name)
    if promo_code is None or not promo_code["active"]:
        result = {
            "status": 1
        }
    else:
        result = {
            "status": 0,
            "coupon_name": coupon.coupon_name,
            "amount_off": coupon.amount_off if coupon.amount_off is not None else 0.0,
            "percent_off": coupon.percent_off if coupon.percent_off is not None else 0.0
        }

    return JSONResponse(content=jsonable_encoder(result))


def is_active_order(order: models.orders.Order) -> bool:
    now = datetime.now()
    difference = now - order.order_date
    return difference.days < 15


def to_order_dict(order: models.orders.Order, db: Session) -> Dict[str, Any]:
    recipes = json.loads(order.recipes)
    recipe_prices: List[Union[RecipePrice, None]] = [
        db.query(RecipePrice).filter(
            and_(RecipePrice.recipe_id == recipe_id, RecipePrice.serving_size == recipes[recipe_id])).first()
        for recipe_id in recipes.keys()]
    recipe_prices_mapping: Dict[int, Dict[int, float]] = reduce(lambda d1, d2: {**d1, **d2},
                                                                [{x.recipe_id: {x.serving_size: x.price}} for x in
                                                                 recipe_prices if x is not None], {})

    recipe_info: Dict[str, Dict[str, Any]] = reduce(lambda d1, d2: {**d1, **d2}, [
        {x.name: {"id": x.id, "image_url": x.image_url, "serving_size": recipes[str(x.id)],
                  "price": recipe_prices_mapping[x.id][recipes[str(x.id)]]}} for x in
        db.query(Recipe).filter(Recipe.id.in_(recipes.keys())).all()], {})

    return {
        "order_number": order.user_facing_order_id,
        "order_breakdown": json.loads(order.order_breakdown_dollars),
        "order_date": order.order_date,
        "order_recipient_name": order.recipient_first_name + " " + order.recipient_last_name,
        "order_delivery_address": order.delivery_address,
        "order_total_dollars": order.order_total_dollars,
        "order_delivered": order.delivered,
        "recipes": recipe_info
    }


def is_known_verification_code(verification_code: str, db: Session) -> bool:
    verified_user = db.query(VerifiedSignUp).filter(VerifiedSignUp.verification_code == verification_code).first()
    if verified_user is None:
        unverified_user = db.query(UnverifiedSignUp).filter(
            UnverifiedSignUp.verification_code == verification_code).first()
        if unverified_user is None:
            return False
    return True
