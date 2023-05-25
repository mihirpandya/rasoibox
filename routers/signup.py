import logging
import sqlite3
from datetime import datetime
from smtplib import SMTP
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import and_
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from api.event import SiteEvent
from api.signup import SignUpViaEmail
from config import Settings
from dependencies.database import get_db
from dependencies.events import emit_event
from emails.base import VerifySignUpEmail, send_email
from models.signups import VerifiedSignUp, UnverifiedSignUp

logger = logging.getLogger("rasoibox")
settings: Settings = Settings()
smtp_server: SMTP = SMTP('smtp.gmail.com', 587)
jinjaEnv = Environment(loader=FileSystemLoader("templates"), autoescape=select_autoescape())

router = APIRouter(
    prefix="/api",
    tags=["recipe"]
)


@router.post("/event")
async def event(site_event: SiteEvent, db: Session = Depends(get_db)):
    emit_event(db, site_event.event_type, site_event.event_date, site_event.verification_code, site_event.referrer)
    return


@router.post("/signup/email")
async def signup_via_email(sign_up_via_email: SignUpViaEmail, db: Session = Depends(get_db)):
    try:
        verified_sign_up: Optional[VerifiedSignUp] = db.query(VerifiedSignUp).filter(
            and_(VerifiedSignUp.email == sign_up_via_email.email,
                 VerifiedSignUp.zipcode == sign_up_via_email.zipcode)).first()

        if verified_sign_up is not None:
            logger.info("User already verified.")

            return JSONResponse(content=jsonable_encoder({
                "status": 0,
                "message": "User already verified.",
                "verification_code": verified_sign_up.verification_code
            }))

        unverified_sign_up: Optional[UnverifiedSignUp] = db.query(UnverifiedSignUp).filter(
            and_(UnverifiedSignUp.email == sign_up_via_email.email,
                 UnverifiedSignUp.zipcode == sign_up_via_email.zipcode)).first()

        message: str
        status_code: int
        verification_code: str
        if unverified_sign_up is not None:
            logger.info("User already signed up but not verified. Resending verification email.")
            verification_code = unverified_sign_up.verification_code
            status_code = 1
            message = "User already signed up but not verified. Verification email re-sent"
        else:
            verification_code = sign_up_via_email.verification_code
            status_code = 2
            message = "Verification email sent"
            emit_event(db, "NEW_SIGN_UP", sign_up_via_email.signup_date, sign_up_via_email.verification_code,
                       sign_up_via_email.referrer)

            # insert entry in db
            db.add(
                UnverifiedSignUp(
                    email=sign_up_via_email.email,
                    signup_date=sign_up_via_email.signup_date,
                    signup_from="EMAIL",
                    zipcode=sign_up_via_email.zipcode,
                    verification_code=verification_code,
                )
            )

            db.commit()

        # send email with verification link
        url_base: str = settings.frontend_url_base[0:-1] if settings.frontend_url_base.endswith(
            "/") else settings.frontend_url_base
        verification_email: VerifySignUpEmail = VerifySignUpEmail(url_base,
                                                                  verification_code,
                                                                  sign_up_via_email.email,
                                                                  settings.from_email)

        # send email best effort
        try:
            send_email(jinjaEnv, verification_email, smtp_server, settings.email, settings.email_app_password)
        except Exception as e:
            logger.error("Failed to send email.")
            logger.error(e)

        return JSONResponse(content={"status": status_code, "message": message, "verification_code": verification_code})
    except sqlite3.OperationalError as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Failed to save data.")


@router.get("/verify/email")
async def verify_email(id: str, db: Session = Depends(get_db)) -> JSONResponse:
    unverified_sign_up: Optional[UnverifiedSignUp] = db.query(UnverifiedSignUp).filter(
        UnverifiedSignUp.verification_code == id).first()

    if unverified_sign_up is not None:
        verify_date = datetime.now()
        db.add(
            VerifiedSignUp(
                email=unverified_sign_up.email,
                signup_date=unverified_sign_up.signup_date,
                signup_from=unverified_sign_up.signup_from,
                zipcode=unverified_sign_up.zipcode,
                verify_date=verify_date,
                verification_code=unverified_sign_up.verification_code
            )
        )

        db.delete(unverified_sign_up)
        db.commit()
        emit_event(db, "VERIFY", verify_date, unverified_sign_up.verification_code, None)

    verified_sign_up: Optional[VerifiedSignUp] = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.verification_code == id).first()
    if verified_sign_up is not None:
        return JSONResponse(content=jsonable_encoder({}))
    else:
        raise HTTPException(status_code=404, detail="Invalid verification code.")


@router.get("/verified")
async def is_verified_sign_up(id: str, db: Session = Depends(get_db)) -> JSONResponse:
    verified_sign_up: Optional[VerifiedSignUp] = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.verification_code == id).first()

    verified: bool = True if verified_sign_up is not None else False

    return JSONResponse(content=jsonable_encoder({"verified": verified}))