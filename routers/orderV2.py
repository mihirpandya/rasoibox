import json
import logging
import random
import string
from datetime import datetime
from functools import reduce
from typing import List, Dict

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from stripe.error import SignatureVerificationError
from stripe.stripe_object import StripeObject

import api
import models
from api.orders import CartItem, Order
from config import Settings
from dependencies.customers import get_current_customer
from dependencies.database import get_db
from dependencies.stripe_utils import create_payment_intent, \
    get_payment_intent, modify_payment_intent
from models.customers import Customer
from models.orders import Cart, Order
from models.orders import Cart, PromoCode, PaymentStatusEnum
from models.recipes import RecipePrice
from models.signups import VerifiedSignUp
from routers.order import send_receipt_email_best_effort, to_order_dict, complete_invitation

logger = logging.getLogger("rasoibox")

router = APIRouter(
    prefix="/api/orderV2",
    tags=["order"]
)

settings: Settings = Settings()


def generate_order_id() -> str:
    res = ''.join(random.choices(string.digits, k=8))
    return res.lower()


@router.post("/initiate_intent")
async def initiate_intent(current_customer: Customer = Depends(get_current_customer),
                          db: Session = Depends(get_db)):
    existing_order = db.query(models.orders.Order).filter(
        and_(models.orders.Order.customer == current_customer.id,
             models.orders.Order.payment_status == PaymentStatusEnum.INITIATED)).first()

    user_facing_order_id: str
    payment_intent: StripeObject
    if existing_order is not None:
        user_facing_order_id = existing_order.user_facing_order_id
        payment_intent = get_payment_intent(existing_order.payment_intent)
        # TODO: trigger new payment intent depending on previous payment intent status
    else:
        user_facing_order_id: str = generate_order_id()
        payment_intent = create_payment_intent(100, user_facing_order_id)

        db.add(models.orders.Order(
            user_facing_order_id=user_facing_order_id,
            order_date=datetime.now(),
            recipes=json.dumps({}),
            recipient_first_name="",
            recipient_last_name="",
            payment_status=PaymentStatusEnum.INITIATED,
            customer=current_customer.id,
            delivered=False,
            order_total_dollars=1,
            order_breakdown_dollars=json.dumps({}),
            delivery_address=json.dumps({}),
            phone_number="",
            promo_codes=json.dumps({}),
            payment_intent=payment_intent.stripe_id
        ))

        db.commit()

    return JSONResponse(
        content=jsonable_encoder({"client_secret": payment_intent.client_secret, "order_id": user_facing_order_id}))


@router.post("/initiate_place_order")
async def initiate_place_order(order: api.orders.Order, current_customer: Customer = Depends(get_current_customer),
                               db: Session = Depends(get_db)):
    verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.email == current_customer.email).first()
    if verified_sign_up is None:
        raise HTTPException(status_code=400, detail="User is not verified.")

    existing_order: Order = db.query(Order).filter(
        and_(Order.customer == current_customer.id, Order.payment_status == PaymentStatusEnum.INITIATED)).first()

    if existing_order is None:
        raise HTTPException(status_code=400, detail="Order intent not found.")

    payment_intent: StripeObject = get_payment_intent(existing_order.payment_intent)

    if payment_intent is None or payment_intent.status != "requires_payment_method":
        logger.error("Invalid payment intent: {}".format(payment_intent))
        raise HTTPException(status_code=400, detail="Invalid payment intent")

    cart_items_by_recipe_id: Dict[int, Cart] = reduce(lambda d1, d2: {**d1, **d2},
                                                      [{x.recipe_id: x} for x in db.query(Cart).filter(
                                                          Cart.verification_code == verified_sign_up.verification_code)
                                                      .all()], {})

    if len(cart_items_by_recipe_id.keys()) > 2:
        raise HTTPException(status_code=400, detail="Too many items in cart.")

    promo_codes: List[PromoCode] = db.query(PromoCode).filter(
        and_(PromoCode.promo_code_name.in_(order.promo_codes),
             PromoCode.redeemable_by_verification_code == verified_sign_up.verification_code)).all()
    if len(promo_codes) is not len(order.promo_codes):
        raise HTTPException(status_code=400, detail="Invalid promo codes.")

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
    for promo_code in promo_codes:
        if promo_code.amount_off is not None and promo_code.amount_off > 0:
            order_total_dollars = order_total_dollars - promo_code.amount_off
        elif promo_code.percent_off is not None and promo_code.percent_off > 0:
            order_total_dollars = (1.0 - (promo_code.percent_off / 100.0)) * order_total_dollars
    order_breakdown_dollars = reduce(lambda d1, d2: {**d1, **d2}, [{x.id: x.price} for x in recipe_prices_ordered], {})
    order_breakdown = {
        "items": order_breakdown_dollars,
        "promo_codes": [{"name": x.promo_code_name, "amount_off": x.amount_off, "percent_off": x.percent_off} for x in
                        promo_codes]
    }
    order_total_cents: int = int(order_total_dollars * 100)

    modified_intent = modify_payment_intent(payment_intent.stripe_id, order_total_cents,
                                            existing_order.user_facing_order_id,
                                            order_breakdown)

    if modified_intent is None or modified_intent.amount != order_total_cents:
        logger.error("Failed to modify intent: {}".format(modified_intent))
        raise HTTPException(status_code=400, detail="Failed to modify intent.")

    order_updates = {
        Order.recipes: json.dumps(recipes_serving_size_map),
        Order.recipient_first_name: order.recipient_first_name,
        Order.recipient_last_name: order.recipient_last_name,
        Order.order_total_dollars: round(order_total_dollars, 2),
        Order.order_breakdown_dollars: json.dumps(order_breakdown),
        Order.delivery_address: jsonable_encoder(order.delivery_address),
        Order.phone_number: order.phone_number,
        Order.promo_codes: json.dumps([x.id for x in promo_codes])
    }

    db.query(Order).filter(and_(Order.user_facing_order_id == existing_order.user_facing_order_id,
                                Order.payment_status == PaymentStatusEnum.INITIATED)).update(order_updates)

    promo_code_names = [x.promo_code_name for x in promo_codes]
    db.query(PromoCode).filter(and_(PromoCode.promo_code_name.in_(promo_code_names),
                                    PromoCode.redeemable_by_verification_code == verified_sign_up.verification_code)) \
        .update({PromoCode.number_times_redeemed: PromoCode.number_times_redeemed + 1})

    db.commit()

    return


@router.post("/webhook_complete_order")
async def webhook_complete_order(request: Request, db: Session = Depends(get_db)):
    request_body = await request.json()

    stripe_signature = request.headers['STRIPE_SIGNATURE']

    try:
        event = stripe.Webhook.construct_event(request_body, stripe_signature,
                                               settings.stripe_payment_success_webhook_secret)
        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']

            complete_order(payment_intent['id'], payment_intent['metadata']['user_facing_order_id'],
                           payment_intent['amount'], db)

            return JSONResponse(content=jsonable_encoder({"success": True}))
        else:
            logger.warning(event)
            raise HTTPException(status_code=400, detail="Unrecognized event")
    except ValueError as e:
        # Invalid payload
        logger.error(e)
        raise HTTPException(status_code=400, detail="Invalid payload")
    except SignatureVerificationError as e:
        # Invalid signature
        logger.error("Invalid signature: {}".format(stripe_signature))
        logger.error(e)
        raise HTTPException(status_code=403, detail="Invalid signature")


def complete_order(payment_intent_id: str, user_facing_order_id: str, amount_cents: int, db: Session):
    amount_dollars: float = float(amount_cents) / 100.0
    order: Order = db.query(Order).filter(
        and_(Order.payment_intent == payment_intent_id, Order.user_facing_order_id == user_facing_order_id)).first()

    if order is None:
        raise HTTPException(status_code=404, detail="Unknown order")

    if order.payment_status != PaymentStatusEnum.INITIATED:
        logger.error("Order not in initiated state.: {}".format(order))
        raise HTTPException(status_code=400, detail="Order not in initiated state.")

    if order.order_total_dollars != amount_dollars:
        logger.error("Order total does not match: {} {}".format(order.order_total_dollars, amount_dollars))
        raise HTTPException(status_code=400, detail="Order total does not match.")

    current_customer: Customer = db.query(Customer).filter(Customer.id == order.customer).first()
    if current_customer is None:
        logger.error("Could not find customer: {}".format(order))
        raise HTTPException(status_code=400, detail="Could not find customer.")

    verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.email == current_customer.email).first()
    if verified_sign_up is None:
        logger.error("Customer is not verified: {}".format(current_customer))
        raise HTTPException(status_code=400, detail="Customer is not verified.")

    db.query(models.orders.Order).filter(Order.user_facing_order_id == order.user_facing_order_id).update(
        {Order.payment_status: PaymentStatusEnum.COMPLETED})
    db.query(Cart).filter(Cart.verification_code == verified_sign_up.verification_code).delete()
    db.commit()

    order: Order = db.query(models.orders.Order).filter(
        Order.user_facing_order_id == order.user_facing_order_id).first()

    # send email
    result = to_order_dict(order, db, customer_email=current_customer.email)
    send_receipt_email_best_effort(current_customer.email, current_customer.first_name, result)

    # complete invite friend
    complete_invitation(current_customer, db)
