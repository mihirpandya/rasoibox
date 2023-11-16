import json
import logging
from functools import reduce
from typing import List, Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from config import Settings
from dependencies.database import get_db
from models.customers import Customer
from models.invitations import Invitation, InvitationStatusEnum
from models.orders import PromoCode, Order, Cart
from models.recipes import RecipePrice
from models.signups import VerifiedSignUp

logger = logging.getLogger("rasoibox")

router = APIRouter(
    prefix="/api/rewards",
    tags=["rewards"]
)

settings: Settings = Settings()


@router.get("/get_all_rewards")
async def get_all_rewards(verification_code: str, db: Session = Depends(get_db)):
    verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.verification_code == verification_code).first()
    result: List[Dict[Any, Any]] = []
    if verified_sign_up is not None:
        promo_codes: List[PromoCode] = db.query(PromoCode).filter(and_(
            PromoCode.redeemable_by_verification_code == verification_code, PromoCode.number_times_redeemed == 0)).all()
        customer: Customer = db.query(Customer).filter(Customer.email == verified_sign_up.email).first()
        orders: List[Order] = []
        if customer is not None:
            orders = db.query(Order).filter(Order.customer == customer.id).all()
        order_breakdown = [(x.user_facing_order_id, json.loads(x.order_breakdown_dollars)) for x in orders]
        order_to_promo: Dict[str, str] = reduce(lambda d1, d2: {**d1, **d2},
                                                [{x[1]["promo_codes"][0]["name"]: x[0]} for x in order_breakdown if
                                                 len(x[1]["promo_codes"]) == 1], {})
        for promo_code in promo_codes:
            promo_object = {
                "promo_code": promo_code.promo_code_name
            }

            if promo_code.amount_off is not None and promo_code.amount_off > 0:
                promo_object["amount_off"] = promo_code.amount_off
            if promo_code.percent_off is not None and promo_code.percent_off > 0:
                promo_object["percent_off"] = promo_code.percent_off

            if promo_code.promo_code_name in order_to_promo:
                promo_object["order_id"] = order_to_promo[promo_code.promo_code_name]
                promo_object["status"] = "Redeemed"
            else:
                promo_object["status"] = "Redeemable"

            result.append(promo_object)

    pending_invitations: List[Invitation] = db.query(Invitation).filter(
        and_(Invitation.referrer_verification_code == verification_code,
             Invitation.invitation_status == InvitationStatusEnum.INVITED)).all()
    for pending_invitation in pending_invitations:
        result.append({
            "promo_code": "{} refer".format(pending_invitation.email),
            "percent_off": 20,
            "status": "Pending"
        })

    result.reverse()
    return JSONResponse(content=jsonable_encoder(result))


@router.post("/site_wide_promos")
async def get_site_wide_promos(verification_code: str, applied_promo_code_names: List[str],
                               db: Session = Depends(get_db)):
    applied_promo_codes: List[PromoCode] = db.query(PromoCode).filter(
        PromoCode.promo_code_name.in_(applied_promo_code_names)).all()

    if applied_promo_codes is None or len(applied_promo_codes) != len(applied_promo_code_names):
        raise HTTPException(status_code=400, detail="Invalid promo code.")

    promo_codes: List[PromoCode] = all_site_wide_promos(verification_code, applied_promo_codes, db)
    result = [{"name": x.promo_code_name, "amount_off": x.amount_off, "percent_off": x.percent_off} for x in
              promo_codes]
    return JSONResponse(content=jsonable_encoder(result))


def all_site_wide_promos(verification_code: str, applied_promo_codes: List[PromoCode], db: Session) -> List[PromoCode]:
    cart: List[Cart] = db.query(Cart).filter(Cart.verification_code == verification_code).all()

    subtotal: float = 0
    for item in cart:
        recipe_price: RecipePrice = db.query(RecipePrice).filter(
            and_(RecipePrice.recipe_id == item.recipe_id, RecipePrice.serving_size == item.serving_size)).first()
        if recipe_price is None:
            raise HTTPException(status_code=404, detail="Unknown item in cart")
        subtotal = subtotal + recipe_price.price

    for promo_code in applied_promo_codes:
        if promo_code.amount_off is not None and promo_code.amount_off > 0:
            subtotal = subtotal - promo_code.amount_off
        elif promo_code.percent_off is not None and promo_code.percent_off > 0:
            subtotal = (1.0 - (promo_code.percent_off / 100.0)) * subtotal

    # diwali promotion
    # diwali_promo_code: Optional[PromoCode] = None
    # if subtotal >= 80.0:
    #     diwali_promo_code = db.query(PromoCode).filter(and_(PromoCode.promo_code_name == "DIWALI20",
    #                                                         PromoCode.redeemable_by_verification_code == "INTERNAL")).first()
    # elif subtotal >= 60.0:
    #     diwali_promo_code = db.query(PromoCode).filter(and_(PromoCode.promo_code_name == "DIWALI10",
    #                                                         PromoCode.redeemable_by_verification_code == "INTERNAL")).first()
    # elif subtotal >= 40.0:
    #     diwali_promo_code = db.query(PromoCode).filter(and_(PromoCode.promo_code_name == "DIWALI5",
    #                                                         PromoCode.redeemable_by_verification_code == "INTERNAL")).first()
    #
    # if diwali_promo_code is not None:
    #     return [diwali_promo_code]
    # else:
    #     return []
    return []
