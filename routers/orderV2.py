import json
import logging
import random
import string
from datetime import datetime
from functools import reduce
from typing import List, Dict, Optional
import api
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from stripe.error import SignatureVerificationError
from stripe.stripe_object import StripeObject

from config import Settings
from dependencies.customers import get_current_customer
from dependencies.database import get_db
from dependencies.stripe_utils import create_payment_intent, \
    get_payment_intent, modify_payment_intent
from emails.base import send_email
from emails.createpassword import CreatePasswordEmail
from models.customers import Customer
from models.orders import Cart, Order
from models.orders import Cart, PromoCode, PaymentStatusEnum
from models.recipes import RecipePrice
from models.signups import VerifiedSignUp
from routers.order import send_receipt_email_best_effort, to_order_dict, complete_invitation
from routers.signup import jinjaEnv, smtp_server

logger = logging.getLogger("rasoibox")

router = APIRouter(
    prefix="/api/orderV2",
    tags=["order"]
)

settings: Settings = Settings()


def generate_order_id() -> str:
    res = ''.join(random.choices(string.digits, k=8))
    return res.lower()


def get_or_create_customer_from_verification_code(verification_code: str, order: api.orders.Order,
                                                  db: Session) -> Customer:
    verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.verification_code == verification_code).first()
    customer: Optional[Customer] = None
    if verified_sign_up is not None:
        customer = db.query(Customer).filter(Customer.email == VerifiedSignUp.email).first()

    if customer is None:
        db.add(Customer(
            first_name=order.recipient_first_name,
            last_name=order.recipient_last_name,
            email=order.email,
            verified=False,
            join_date=datetime.now()
        ))
        db.commit()
        customer = db.query(Customer).filter(Customer.email == order.email).first()

    return customer


@router.post("/initiate_intent")
async def initiate_intent(verification_code: str, db: Session = Depends(get_db)):
    existing_order = db.query(Order).filter(
        and_(Order.verification_code == verification_code, Order.payment_status == PaymentStatusEnum.INITIATED)).first()

    user_facing_order_id: str
    payment_intent: StripeObject
    if existing_order is not None:
        user_facing_order_id = existing_order.user_facing_order_id
        payment_intent = get_payment_intent(existing_order.payment_intent)
        # TODO: trigger new payment intent depending on previous payment intent status
    else:
        user_facing_order_id: str = generate_order_id()
        payment_intent = create_payment_intent(100, user_facing_order_id)

        db.add(Order(
            user_facing_order_id=user_facing_order_id,
            order_date=datetime.now(),
            recipes=json.dumps({}),
            recipient_first_name="",
            recipient_last_name="",
            payment_status=PaymentStatusEnum.INITIATED,
            customer=0,
            verification_code=verification_code,
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
async def initiate_place_order(order: api.orders.Order, verification_code: str, db: Session = Depends(get_db)):
    existing_order: Order = db.query(Order).filter(
        and_(Order.verification_code == verification_code, Order.payment_status == PaymentStatusEnum.INITIATED)).first()

    if existing_order is None:
        raise HTTPException(status_code=400, detail="Order intent not found.")

    payment_intent: StripeObject = get_payment_intent(existing_order.payment_intent)

    if payment_intent is None or payment_intent.status != "requires_payment_method":
        logger.error("Invalid payment intent: {}".format(payment_intent))
        raise HTTPException(status_code=400, detail="Invalid payment intent")

    cart_items_by_recipe_id: Dict[int, Cart] = reduce(lambda d1, d2: {**d1, **d2},
                                                      [{x.recipe_id: x} for x in db.query(Cart).filter(
                                                          Cart.verification_code == verification_code)
                                                      .all()], {})

    # if len(cart_items_by_recipe_id.keys()) > 2:
    #     raise HTTPException(status_code=400, detail="Too many items in cart.")

    promo_codes: List[PromoCode] = db.query(PromoCode).filter(PromoCode.promo_code_name.in_(order.promo_codes)).all()

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
    order_total_cents: int = int(order_total_dollars * 1000 / 10)

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
        Order.recipient_email: order.email,
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
                                    PromoCode.redeemable_by_verification_code == verification_code)) \
        .update({PromoCode.number_times_redeemed: PromoCode.number_times_redeemed + 1})

    db.commit()

    return


@router.post("/webhook_complete_order")
async def webhook_complete_order(request: Request, db: Session = Depends(get_db)):
    request_body = await request.body()

    stripe_signature = request.headers['stripe-signature']

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


@router.get("/get_order_from_intent")
async def get_order_from_payment_intent(order_id: str, payment_intent: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(
        and_(Order.user_facing_order_id == order_id, Order.payment_intent == payment_intent)).first()

    if order is None:
        raise HTTPException(status_code=404, detail="Unknown order")

    return JSONResponse(content=jsonable_encoder(to_order_dict(order, db, customer_email=order.recipient_email)))


@router.post("/email_orders_without_accounts")
async def email_orders_without_accounts(db: Session = Depends(get_db)):
    customers: List[Customer] = db.query(Customer).filter(Customer.hashed_password.is_(None)).all()
    emails: List[(int, str)] = []
    for customer in customers:
        order: Order = db.query(Order).filter(
            and_(Order.customer == customer.id, Order.payment_status == PaymentStatusEnum.COMPLETED)).first()
        if order is None:
            logger.warning("Could not find order for customer without password: {}".format(customer.id))
        else:
            emails.append((order.customer, order.payment_intent))
            try:
                url_base: str = settings.frontend_url_base[0:-1] if settings.frontend_url_base.endswith(
                    "/") else settings.frontend_url_base
                create_password_email: CreatePasswordEmail = CreatePasswordEmail(
                    url_base=url_base,
                    first_name=order.recipient_first_name,
                    create_id=order.customer,
                    payment_intent=order.payment_intent,
                    to_email=order.recipient_email,
                    from_email=settings.from_email
                )
                send_email(jinjaEnv, create_password_email, smtp_server, settings.email, settings.email_app_password)
            except Exception as e:
                logger.error("Could not email: {}".format(order.recipient_email))
                logger.error(e)

    return JSONResponse(jsonable_encoder(emails))


@router.post("/admin_webhook_complete_order")
async def admin_webhook_complete_order(payment_intent_id: str, user_facing_order_id: str, amount_cents: int,
                                       db: Session = Depends(get_db)):
    return complete_order(payment_intent_id, user_facing_order_id, amount_cents, db)


def complete_order(payment_intent_id: str, user_facing_order_id: str, amount_cents: int, db: Session):
    now = datetime.now()
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
    create_account_email: bool = False
    if current_customer is None:
        logger.info("Order placed by guest.")
        create_account_email = True
        db.add(
            Customer(
                first_name=order.recipient_first_name,
                last_name=order.recipient_last_name,
                email=order.recipient_email,
                verified=True,
                join_date=now,
                last_updated=now
            )
        )
        db.commit()
        current_customer = db.query(Customer).filter(Customer.email == order.recipient_email).first()

        verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(
            VerifiedSignUp.verification_code == order.verification_code).first()
        if verified_sign_up is None:
            zipcode: str = order.delivery_address['zipcode']
            db.add(
                VerifiedSignUp(
                    email=order.recipient_email,
                    signup_date=now,
                    signup_from="GUEST_ORDER",
                    verify_date=now,
                    zipcode=zipcode,
                    verification_code=order.verification_code
                )
            )

    db.query(Order).filter(Order.user_facing_order_id == order.user_facing_order_id).update(
        {
            Order.payment_status: PaymentStatusEnum.COMPLETED,
            Order.customer: current_customer.id
        })
    db.query(Cart).filter(Cart.verification_code == order.verification_code).delete()
    db.commit()

    order: Order = db.query(Order).filter(
        Order.user_facing_order_id == order.user_facing_order_id).first()

    # send emails
    result = to_order_dict(order, db, customer_email=order.recipient_email)
    send_receipt_email_best_effort(order.recipient_email, order.recipient_first_name, result)

    # complete invite friend
    complete_invitation(current_customer, db)
