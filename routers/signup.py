import logging
import sqlite3
from datetime import datetime
from smtplib import SMTP
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import and_
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from api.event import SiteEvent
from api.signup import SignUpViaEmail, AddDeliverableZipcodes
from config import Settings
from dependencies.database import get_db
from dependencies.events import emit_event
from dependencies.signup import generate_verification_code
from emails.base import send_email
from emails.verifysignup import VerifySignUpEmail
from models.customers import Customer
from models.invitations import Invitation
from models.signups import VerifiedSignUp, UnverifiedSignUp, DeliverableZipcode

logger = logging.getLogger("rasoibox")
settings: Settings = Settings()
smtp_server: SMTP = SMTP('smtp.gmail.com', 587)
jinjaEnv = Environment(loader=FileSystemLoader("templates"), autoescape=select_autoescape())

router = APIRouter(
    prefix="/api",
    tags=["signup"]
)


def send_verify_email(email: str, verification_code: str):
    # send email with verification link
    url_base: str = settings.frontend_url_base[0:-1] if settings.frontend_url_base.endswith(
        "/") else settings.frontend_url_base
    verification_email: VerifySignUpEmail = VerifySignUpEmail(url_base,
                                                              verification_code,
                                                              email,
                                                              settings.from_email)

    # send email best effort
    try:
        send_email(jinjaEnv, verification_email, smtp_server, settings.email, settings.email_app_password)
    except Exception as e:
        logger.error("Failed to send email.")
        logger.error(e)


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

        # if email and verification code is same as an existing invitation code and email,
        # this should already be considered verified
        invitation: Optional[Invitation] = db.query(Invitation).filter(
            and_(Invitation.email == sign_up_via_email.email,
                 Invitation.referred_verification_code == sign_up_via_email.verification_code)).first()
        if invitation is not None:
            logger.info("User has been invited. Marking as verified.")

            emit_event(db, "INVITATION_SIGN_UP", sign_up_via_email.signup_date, sign_up_via_email.verification_code,
                       sign_up_via_email.referrer)

            db.add(
                VerifiedSignUp(
                    email=sign_up_via_email.email,
                    signup_date=sign_up_via_email.signup_date,
                    signup_from="INVITATION",
                    verify_date=sign_up_via_email.signup_date,
                    zipcode=sign_up_via_email.zipcode,
                    verification_code=sign_up_via_email.verification_code
                )
            )

            db.commit()

            return JSONResponse(content=jsonable_encoder({
                "status": 3,
                "message": "User has been invited. Marking as verified.",
                "verification_code": sign_up_via_email.verification_code
            }))

        unverified_sign_up: Optional[UnverifiedSignUp] = db.query(UnverifiedSignUp).filter(
            UnverifiedSignUp.email == sign_up_via_email.email).first()

        message: str
        status_code: int
        verification_code: str
        if unverified_sign_up is not None:
            logger.info("User already signed up but not verified. Resending verification email.")
            verification_code = unverified_sign_up.verification_code
            status_code = 1
            message = "User already signed up but not verified. Verification email re-sent"
        else:
            # check if same person trying to sign up with different email
            # generate new verification code if so
            unverified_sign_up: Optional[UnverifiedSignUp] = db.query(UnverifiedSignUp).filter(
                UnverifiedSignUp.verification_code == sign_up_via_email.verification_code).first()
            verified_sign_up: Optional[VerifiedSignUp] = db.query(VerifiedSignUp).filter(
                VerifiedSignUp.verification_code == sign_up_via_email.verification_code).first()
            if unverified_sign_up is not None or verified_sign_up is not None:
                verification_code = generate_verification_code()
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

        send_verify_email(sign_up_via_email.email, verification_code)

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

        customer: Customer = db.query(Customer).filter(Customer.email == unverified_sign_up.email).first()
        if customer is not None:
            db.query(Customer).filter(Customer.email == unverified_sign_up.email).update({'verified': True})

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
    response = {"verified": verified}
    if verified:
        response["email"] = verified_sign_up.email
        response["zipcode"] = verified_sign_up.zipcode
    else:
        invitation = db.query(Invitation).filter(Invitation.referred_verification_code == id).first()
        if invitation is not None:
            response["email"] = invitation.email

    return JSONResponse(content=jsonable_encoder(response))


@router.get("/in_deliverable_zipcode")
async def in_deliverable_zipcode(id: str, db: Session = Depends(get_db)):
    verified_sign_up = db.query(VerifiedSignUp).filter(VerifiedSignUp.verification_code == id).first()

    zipcode = None
    if verified_sign_up is not None:
        zipcode = verified_sign_up.zipcode
    else:
        unverified_sign_up = db.query(UnverifiedSignUp).filter(UnverifiedSignUp.verification_code == id).first()
        if unverified_sign_up is not None:
            zipcode = unverified_sign_up.zipcode

    result = {}
    if zipcode is not None:
        deliverable_zipcode = db.query(DeliverableZipcode).filter(DeliverableZipcode.zipcode == zipcode).first()
        if deliverable_zipcode is not None:
            result["status"] = 0
            result["delivery_start_date"] = deliverable_zipcode.delivery_start_date
            result["zipcode"] = deliverable_zipcode.zipcode
        else:
            result["status"] = -1
    else:
        result["status"] = -2

    return JSONResponse(content=jsonable_encoder(result))


@router.get("/is_deliverable_zipcode")
async def is_deliverable_zipcode(zipcode: str, db: Session = Depends(get_db)):
    result = {}
    deliverable_zipcode = db.query(DeliverableZipcode).filter(DeliverableZipcode.zipcode == zipcode).first()
    if deliverable_zipcode is not None:
        result["status"] = 0
        result["delivery_start_date"] = deliverable_zipcode.delivery_start_date
        result["zipcode"] = deliverable_zipcode.zipcode
    else:
        emit_event(db, "OUTSIDE_DELIVERY", datetime.now(), None, zipcode)
        result["status"] = -1

    return JSONResponse(content=jsonable_encoder(result))


@router.post("/add_deliverable_zipcodes")
async def add_deliverable_zipcodes(zipcodes: AddDeliverableZipcodes, db: Session = Depends(get_db)):
    now = datetime.now()
    existing_zipcodes: List[str] = [x.zipcode for x in db.query(DeliverableZipcode).filter(
        DeliverableZipcode.zipcode.in_(zipcodes.zipcodes)).all()]

    new_zipcodes: List[DeliverableZipcode] = [DeliverableZipcode(zipcode=x, delivery_start_date=now) for x in
                                              zipcodes.zipcodes if x not in existing_zipcodes]

    if len(new_zipcodes) == 0:
        return

    db.add_all(new_zipcodes)

    db.commit()
