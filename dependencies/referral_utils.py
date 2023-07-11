import logging
from datetime import datetime
from random import random

from fastapi import HTTPException
from sqlalchemy.orm import Session

from dependencies.stripe_utils import create_promo_code_from_coupon, find_promo_code_id
from models.orders import PromoCode

logger = logging.getLogger("rasoibox")


def generate_promo_code(first_name: str) -> str:
    return (first_name + "0" + "{0:x}".format(int(random() * 10_000))).upper()


def to_dollars(cents):
    if cents is not None:
        return round(cents / 100.0, 2)
    return None


def to_promo_amount_string(promo_code: PromoCode) -> str:
    if promo_code.amount_off is not None:
        return "${:.2f}".format(promo_code.amount_off)
    elif promo_code.percent_off is not None:
        return "{}%".format(int(promo_code.percent_off))


def create_stripe_promo_code(stripe_coupon_id: str, customer_facing_code: str, redeemable_by: str,
                             db: Session) -> PromoCode:
    try:
        create_promo_code_from_coupon(stripe_coupon_id, customer_facing_code)
        promo_code = find_promo_code_id(customer_facing_code)
        if promo_code is None:
            raise HTTPException(status_code=400, detail="Unable to find promo code.")

        if not promo_code.active:
            raise HTTPException(status_code=400, detail="Created promo code is not active.")

        promo_code_db: PromoCode = PromoCode(
            promo_code_name=promo_code.code,
            created_on=datetime.fromtimestamp(promo_code.created),
            number_times_redeemed=0,
            stripe_promo_code_id=promo_code.id,
            amount_off=to_dollars(promo_code.coupon.amount_off),
            percent_off=promo_code.coupon.percent_off,
            redeemable_by_verification_code=redeemable_by
        )

        db.add(promo_code_db)

        db.commit()

        return promo_code_db
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=400, detail="Invalid stripe coupon id {}".format(stripe_coupon_id))
