import logging
import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from config import Settings
from dependencies.database import get_db
from emails.base import send_email
from emails.popfest.preorder1 import PreOrder1Email
from emails.popfest.preorder2 import PreOrder2Email
from models.orders import PromoCode
from models.signups import VerifiedSignUp, UnverifiedSignUp
from routers.signup import jinjaEnv, smtp_server

logger = logging.getLogger("rasoibox")

settings: Settings = Settings()

router = APIRouter(
    prefix="/api/popfest",
    tags=["popfest"]
)


@router.post("/preorder2_test")
async def preorder_2_test(verification_code: str, db: Session = Depends(get_db)):
    verified: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.verification_code == verification_code).first()
    if verified is not None:
        try:
            pre_order_email: PreOrder2Email = PreOrder2Email(verified.email, settings.from_email)
            send_email(jinjaEnv, pre_order_email, smtp_server, settings.email, settings.email_app_password)
        except Exception as e:
            logger.error("Failed to send email.")
            logger.error(e)
    return


@router.post("/preorder2_verified")
async def preorder_2_verified(after_id: int, db: Session = Depends(get_db)):
    all_verified: List[VerifiedSignUp] = db.query(VerifiedSignUp).filter(
        and_(VerifiedSignUp.id > after_id, VerifiedSignUp.signup_from != "GUEST_ORDER")).all()
    all_verified_emails: List[str] = [x.email for x in all_verified]
    logger.info("Verified size: {}".format(len(all_verified)))

    for verified_sign_up in all_verified_emails:
        try:
            pre_order_email: PreOrder2Email = PreOrder2Email(verified_sign_up, settings.from_email)
            send_email(jinjaEnv, pre_order_email, smtp_server, settings.email, settings.email_app_password)
            time.sleep(1)
            logger.info("Email sent to: {}".format(verified_sign_up))
        except Exception as e:
            logger.error("Failed to send email.")
            logger.error(e)


@router.post("/preorder2_unverified")
async def preorder_2_unverified(after_id: int, db: Session = Depends(get_db)):
    all_unverified: List[UnverifiedSignUp] = db.query(UnverifiedSignUp).filter(UnverifiedSignUp.id > after_id).all()
    all_unverified_emails: List[str] = [x.email for x in all_unverified]
    logger.info("Unverified size: {}".format(len(all_unverified)))

    for unverified_sign_up in all_unverified_emails:
        try:
            pre_order_email: PreOrder2Email = PreOrder2Email(unverified_sign_up, settings.from_email)
            send_email(jinjaEnv, pre_order_email, smtp_server, settings.email, settings.email_app_password)
            time.sleep(1)
            logger.info("Email sent to: {}".format(unverified_sign_up))
        except Exception as e:
            logger.error("Failed to send email.")
            logger.error(e)


@router.post("/preorder1")
async def preorder_1(after_id: int, db: Session = Depends(get_db)):
    # all_verified: List[VerifiedSignUp] = db.query(VerifiedSignUp).filter(VerifiedSignUp.id > after_id).all()
    # all_verified_emails: List[str] = [x.email for x in all_verified]
    # logger.info("Verified size: {}".format(len(all_verified)))
    #
    # for verified_sign_up in all_verified_emails:
    #     try:
    #         pre_order_email: PreOrder1Email = PreOrder1Email(verified_sign_up, settings.from_email)
    #         send_email(jinjaEnv, pre_order_email, smtp_server, settings.email, settings.email_app_password)
    #         time.sleep(1)
    #         logger.info("Email sent to: {}".format(verified_sign_up))
    #     except Exception as e:
    #         logger.error("Failed to send email.")
    #         logger.error(e)

    all_unverified: List[UnverifiedSignUp] = db.query(UnverifiedSignUp).filter(UnverifiedSignUp.id > after_id).all()
    all_unverified_emails: List[str] = [x.email for x in all_unverified]
    logger.info("Unverified size: {}".format(len(all_unverified)))

    for unverified_sign_up in all_unverified_emails:
        try:
            pre_order_email: PreOrder1Email = PreOrder1Email(unverified_sign_up, settings.from_email)
            send_email(jinjaEnv, pre_order_email, smtp_server, settings.email, settings.email_app_password)
            time.sleep(1)
            logger.info("Email sent to: {}".format(unverified_sign_up))
        except Exception as e:
            logger.error("Failed to send email.")
            logger.error(e)


@router.get("/is_valid_promo_code")
async def is_valid_promo_code(promo_code: str, db: Session = Depends(get_db)):
    if promo_code == "SCXRB15":
        promo_code: PromoCode = db.query(PromoCode).filter(PromoCode.promo_code_name == promo_code).first()
        if promo_code is not None:
            return JSONResponse(content=jsonable_encoder({
                "status": 0,
                "promo_code_name": promo_code.promo_code_name,
                "amount_off": promo_code.amount_off if promo_code.amount_off is not None else 0.0,
                "percent_off": promo_code.percent_off if promo_code.percent_off is not None else 0.0
            }))
    raise HTTPException(status_code=404, detail="Unknown promo code")


