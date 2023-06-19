import json
import logging
import random
import string
from datetime import datetime
from functools import reduce
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

import models.orders
from api.orders import Order, CartItem, PricedCartItem
from dependencies.customers import get_current_customer
from dependencies.database import get_db
from dependencies.stripe_utils import create_checkout_session
from models.customers import Customer
from models.orders import Cart, Coupon, PaymentStatusEnum
from models.recipes import Recipe, RecipePrice

logger = logging.getLogger("rasoibox")

router = APIRouter(
    prefix="/api/order",
    tags=["order"]
)


def generate_order_id() -> str:
    res = ''.join(random.choices(string.ascii_uppercase +
                                 string.digits, k=10))
    return res.lower()


@router.post("/initiate_place_order")
async def initiate_place_order(order: Order, current_customer: Customer = Depends(get_current_customer),
                               db: Session = Depends(get_db)):
    recipe_names: List[str] = order.recipe_names
    recipe_ids: List[int] = [x.id for x in db.query(Recipe).filter(Recipe.name.in_(recipe_names)).all()]
    if len(recipe_ids) is not len(recipe_names):
        raise HTTPException(status_code=404, detail="Placing order for unknown recipes.")
    cart_items_by_recipe_id: Dict[int, Cart] = reduce(lambda d1, d2: {**d1, **d2},
                                                      [{x.recipe_id: x} for x in db.query(Cart).filter(
                                                          Cart.customer_id == current_customer.id).all()], {})

    coupon_ids: List[int] = [x.id for x in db.query(Coupon).filter(Coupon.coupon_name.in_(order.coupons)).all()]
    if len(coupon_ids) is not len(order.coupons):
        raise HTTPException(status_code=400, detail="Invalid coupons.")

    recipes_serving_size_map: Dict[int, int] = {}
    recipe_prices_ordered: List[RecipePrice] = []

    for recipe_id in recipe_ids:
        if recipe_id not in cart_items_by_recipe_id:
            raise HTTPException(status_code=400, detail="Recipe not in user cart.")
        else:
            serving_size = cart_items_by_recipe_id[recipe_id].serving_size
            recipes_serving_size_map[recipe_id] = serving_size
            recipe_price: RecipePrice = db.query(RecipePrice).filter(
                and_(RecipePrice.recipe_id == recipe_id, RecipePrice.serving_size == serving_size)).first()
            if recipe_price is None:
                raise HTTPException(status_code=404, detail="Invalid recipe serving size combo")
            recipe_prices_ordered.append(recipe_price)
            db.delete(cart_items_by_recipe_id[recipe_id])

    order_total_dollars = reduce(lambda p1, p2: p1 + p2, [x.price for x in recipe_prices_ordered], 0)
    order_breakdown_dollars = reduce(lambda d1, d2: {**d1, **d2}, [{x.id: x.price} for x in recipe_prices_ordered], {})
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
        order_total_dollars=order_total_dollars,
        order_breakdown_dollars=json.dumps(order_breakdown_dollars),
        delivery_address=json.dumps(order.delivery_address),
        phone_number=order.phone_number,
        coupons=json.dumps(coupon_ids)
    ))

    db.commit()

    try:
        checkout_session = create_checkout_session(stripe_price_ids, "/success", "/cancel")
        logger.info("Successfully created checkout session {}".format(checkout_session))
        return JSONResponse(content=jsonable_encoder({"session_url": checkout_session.url}))
    except Exception as e:
        logger.error("Failed to create checkout session.", e)
        db.query(models.orders.Order).filter(and_(models.orders.Order.user_facing_order_id == user_facing_order_id,
                                                  models.orders.Order.order_date == order_date)).update(
            models.orders.Order(
                user_facing_order_id=user_facing_order_id,
                order_date=order_date,
                recipes=json.dumps(recipes_serving_size_map),
                recipient_first_name=order.recipient_first_name,
                recipient_last_name=order.recipient_last_name,
                payment_status=PaymentStatusEnum.FAILED,
                customer=current_customer.id,
                delivered=False,
                order_total_dollars=order_total_dollars,
                order_breakdown_dollars=json.dumps(order_breakdown_dollars),
                delivery_address=json.dumps(order.delivery_address),
                phone_number=order.phone_number,
                coupons=json.dumps(coupon_ids)
            )
        )
        db.commit()
        raise HTTPException(status_code=400, detail="Failed to create Stripe checkout session")


@router.get("/get_cart")
async def get_cart(current_customer: Customer = Depends(get_current_customer),
                   db: Session = Depends(get_db)):
    cart_items: List[Cart] = db.query(Cart).get(Cart.customer_id == current_customer.id).all()
    cart_recipe_ids: List[str] = [x.recipe_id for x in cart_items]
    recipe_names: Dict[int, str] = reduce(lambda d1, d2: {**d1, **d2}, [{x.id: x.name} for x in db.query(Recipe).filter(
        Recipe.id.in_(cart_recipe_ids))], {})
    result: List[PricedCartItem] = []
    for cart_item in cart_items:
        recipe_name = recipe_names[cart_item.recipe_id]
        recipe_price: RecipePrice = db.query(RecipePrice).filter(and_(RecipePrice.recipe_id == cart_item.recipe_id,
                                                                      RecipePrice.serving_size == cart_item.serving_size)).first()
        if recipe_price is None:
            raise HTTPException(status_code=400,
                                detail="Could not find price {}".format(recipe_name))
        result.append(
            PricedCartItem(recipe_name=recipe_name, serving_size=recipe_price.serving_size, price=recipe_price.price))

    return JSONResponse(content=jsonable_encoder(result))


@router.post("/update_cart")
async def update_cart(cart_item: CartItem, current_customer: Customer = Depends(get_current_customer),
                      db: Session = Depends(get_db)):
    recipe: Recipe = db.query(Recipe).filter(Recipe.name == cart_item.recipe_name).first()
    if recipe is None:
        raise HTTPException(status_code=404, detail="Unknown recipe {}".format(cart_item.recipe_name))
    existing_cart_item: Cart = db.query(Cart).filter(
        and_(Cart.recipe_id == recipe.id, Cart.customer_id == current_customer.id)).first()

    if existing_cart_item is None:
        if cart_item.serving_size > 0:
            # add new item
            db.add(Cart(customer_id=current_customer.id, recipe_id=recipe.id, serving_size=cart_item.serving_size))
    else:
        if cart_item.serving_size > 0:
            db.query(Cart).filter(and_(Cart.recipe_id == recipe.id, Cart.customer_id == current_customer.id)).update(
                Cart(customer_id=current_customer.id, recipe_id=recipe.id, serving_size=cart_item.serving_size))
        else:
            db.delete(existing_cart_item)

    db.commit()


@router.get("/get_available_items")
async def get_available_items(_current_customer: Customer = Depends(get_current_customer),
                              db: Session = Depends(get_db)):
    recipe_prices: List[RecipePrice] = db.query(RecipePrice).all()
    recipe_ids: List[int] = list(set([x.recipe_id for x in recipe_prices]))
    recipes: Dict[int, Recipe] = reduce(lambda d1, d2: {**d1, **d2},
                                        [x for x in db.query(Recipe).filter(Recipe.id.in_(recipe_ids))], {})
    result = {}
    for recipe_price in recipe_prices:
        if recipe_price.recipe_id not in recipes:
            raise HTTPException(status_code=400, detail="Unknown recipe {}".format(recipe_price.recipe_id))
        if recipe_price.recipe_id in result:
            result[recipe_price.recipe_id]["serving_sizes"][recipe_price.serving_size] = recipe_price.price
        else:
            recipe: Recipe = recipes[recipe_price.recipe_id]
            result[recipe_price.recipe_id] = {
                "recipe_name": recipe.name,
                "image_url": recipe.image_url,
                "serving_sizes": {
                    recipe_price.serving_size: recipe_price.price
                }
            }

    return JSONResponse(content=jsonable_encoder(result))
