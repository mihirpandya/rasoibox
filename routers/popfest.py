import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config import Settings
from dependencies.database import get_db
from emails.base import send_email
from emails.popfest.preorder1 import PreOrder1Email
from models.signups import VerifiedSignUp, UnverifiedSignUp
from routers.signup import jinjaEnv, smtp_server

logger = logging.getLogger("rasoibox")

settings: Settings = Settings()

router = APIRouter(
    prefix="/api/popfest",
    tags=["popfest"]
)


@router.post("/preorder1")
async def preorder_1(db: Session = Depends(get_db)):
    all_verified = db.query(VerifiedSignUp).all()
    logger.info("Verified size: {}".format(len(all_verified)))
    
    verified_sign_ups: List[VerifiedSignUp] = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.verification_code == "a2a62").all()
    unverified_sign_ups: List[UnverifiedSignUp] = db.query(UnverifiedSignUp).filter(
        UnverifiedSignUp.verification_code == "a2a62").all()
    for verified_sign_up in verified_sign_ups:
        try:
            pre_order_email: PreOrder1Email = PreOrder1Email(verified_sign_up.email, settings.from_email)
            send_email(jinjaEnv, pre_order_email, smtp_server, settings.email, settings.email_app_password)
            logger.info("Email sent to: {}".format(verified_sign_up.email))
        except Exception as e:
            logger.error("Failed to send email.")
            logger.error(e)

    for unverified_sign_up in unverified_sign_ups:
        try:
            pre_order_email: PreOrder1Email = PreOrder1Email(unverified_sign_up.email, settings.from_email)
            send_email(jinjaEnv, pre_order_email, smtp_server, settings.email, settings.email_app_password)
            logger.info("Email sent to: {}".format(unverified_sign_up.email))
        except Exception as e:
            logger.error("Failed to send email.")
            logger.error(e)
