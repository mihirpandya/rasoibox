import json
import logging
from functools import reduce
from typing import List, Any, Dict

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from config import Settings
from dependencies.database import get_db
from models.customers import Customer
from models.invitations import Invitation, InvitationStatusEnum
from models.orders import PromoCode, Order
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
        promo_codes: List[PromoCode] = db.query(PromoCode).filter(
            PromoCode.redeemable_by_verification_code == verification_code).all()
        promo_codes = promo_codes + db.query(PromoCode).filter(
            PromoCode.redeemable_by_verification_code.is_(None)).all()
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
