import logging
import random
import string
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import and_
from sqlalchemy.orm import Session
from starlette import status
from starlette.responses import JSONResponse

from api.customers import CustomerPayload, ChangePasswordPayload, ResetPasswordPayload, UpdateCustomerPayload, \
    CreateAccountFromIntentPayload
from config import Settings
from dependencies.customers import authenticate_customer, get_current_customer, get_password_hash, verify_password, \
    create_access_token
from dependencies.database import get_db
from emails.base import send_email
from emails.resetpassword import ResetPasswordEmail
from emails.resetpasswordcomplete import ResetPasswordCompleteEmail
from emails.verifysignup import VerifySignUpEmail
from models.customers import Customer
from models.invitations import Invitation
from models.orders import PromoCode, Order
from models.reset_passwords import ResetPassword
from models.signups import VerifiedSignUp, UnverifiedSignUp
from routers.signup import jinjaEnv, smtp_server

logger = logging.getLogger("rasoibox")

settings: Settings = Settings()

router = APIRouter(
    prefix="/api/users",
    tags=["users"]
)


class Token(BaseModel):
    access_token: str
    token_type: str
    status: int
    verification_code: str
    first_name: str
    last_name: str
    email: str


def send_verify_email_best_effort(email: str, verification_code: str):
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


def send_reset_password_email_best_effort(email: str, reset_code: str):
    # send email with password reset link
    url_base: str = settings.frontend_url_base[0:-1] if settings.frontend_url_base.endswith(
        "/") else settings.frontend_url_base
    reset_password_email: ResetPasswordEmail = ResetPasswordEmail(url_base,
                                                                  reset_code,
                                                                  email,
                                                                  settings.from_email)

    # send email best effort
    try:
        send_email(jinjaEnv, reset_password_email, smtp_server, settings.email, settings.email_app_password)
    except Exception as e:
        logger.error("Failed to send email.")
        logger.error(e)


def send_reset_password_complete_email_best_effort(email: str, first_name: str):
    reset_password_complete_email: ResetPasswordCompleteEmail = ResetPasswordCompleteEmail(first_name,
                                                                                           email,
                                                                                           settings.from_email)

    # send email best effort
    try:
        send_email(jinjaEnv, reset_password_complete_email, smtp_server, settings.email, settings.email_app_password)
    except Exception as e:
        logger.error("Failed to send email.")
        logger.error(e)


@router.post("/token", response_model=Token)
async def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    clean_email: str = form_data.username.strip()
    clean_email = clean_email.lower()
    customer = authenticate_customer(clean_email, form_data.password, db)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": customer.email})
    verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(VerifiedSignUp.email == customer.email).first()
    customer: Customer = db.query(Customer).filter(Customer.email == customer.email).first()
    return Token(access_token=access_token, token_type="bearer", status=0, first_name=customer.first_name,
                 last_name=customer.last_name, email=customer.email,
                 verification_code=verified_sign_up.verification_code)


@router.post("/check")
async def is_authenticated(current_customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)):
    verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.email == current_customer.email).first()
    return JSONResponse(content=jsonable_encoder({
        "authenticated": True,
        "first_name": current_customer.first_name,
        "last_name": current_customer.last_name,
        "email": current_customer.email,
        "verification_code": verified_sign_up.verification_code
    }))


@router.post("/create")
async def create_user_account(new_customer: CustomerPayload, db: Session = Depends(get_db)) -> JSONResponse:
    existing_customer = db.query(Customer).filter(Customer.email == new_customer.email).first()

    if existing_customer is not None:
        return JSONResponse(content=jsonable_encoder({
            "status": -1,
            "message": "A user with this email already exists."
        }))
    else:
        verified_user = db.query(VerifiedSignUp).filter(VerifiedSignUp.email == new_customer.email).first()
        hashed_password = get_password_hash(new_customer.password)
        verified: bool = verified_user is not None

        # if email and code match an invitation, consider this as a verified sign up
        invitation: Optional[Invitation] = db.query(Invitation).filter(
            and_(Invitation.email == new_customer.email,
                 Invitation.referred_verification_code == new_customer.verification_code)).first()
        if invitation is not None:
            verified = True
            verified_user = VerifiedSignUp(
                email=new_customer.email,
                signup_date=new_customer.join_date,
                signup_from="REFERRED",
                verify_date=new_customer.join_date,
                zipcode=new_customer.zipcode,
                verification_code=new_customer.verification_code
            )
            db.add(verified_user)

        # if email and code match an unverified referrer, consider this as a verified sign up
        unverified_sign_up: Optional[UnverifiedSignUp] = db.query(UnverifiedSignUp).filter(
            and_(UnverifiedSignUp.email == new_customer.email, UnverifiedSignUp.signup_from == "REFERRER")).first()
        if unverified_sign_up is not None and unverified_sign_up.verification_code == new_customer.verification_code:
            verified = True
            verified_user = VerifiedSignUp(
                email=new_customer.email,
                signup_date=unverified_sign_up.signup_date,
                signup_from="REFERRER",
                verify_date=new_customer.join_date,
                zipcode=new_customer.zipcode,
                verification_code=new_customer.verification_code
            )
            db.add(verified_user)
            db.delete(unverified_sign_up)

        db.add(
            Customer(
                first_name=new_customer.first_name,
                last_name=new_customer.last_name,
                email=new_customer.email,
                hashed_password=hashed_password,
                join_date=new_customer.join_date,
                last_updated=new_customer.join_date,
                verified=verified
            )
        )

        if not verified:
            verification_code = new_customer.verification_code
            # add to unverified table
            db.add(
                UnverifiedSignUp(
                    email=new_customer.email,
                    signup_date=new_customer.join_date,
                    signup_from="CREATE_ACCOUNT",
                    zipcode=new_customer.zipcode,
                    verification_code=verification_code,
                )
            )

            send_verify_email_best_effort(new_customer.email, verification_code)

            result = {
                "status": 0,
                "message": "Account created. Verification needed."
            }
        else:
            verification_code = verified_user.verification_code
            result = {
                "status": 1,
                "message": "Account created. No verification needed."
            }

        create_welcome_promo_if_applicable(verification_code, db)

        db.commit()
        return JSONResponse(content=jsonable_encoder(result))


@router.post("/create_account_from_intent")
async def create_user_account_from_intent(new_customer: CreateAccountFromIntentPayload, db: Session = Depends(get_db)):
    customer: Customer = db.query(Customer).filter(Customer.id == new_customer.create_id).first()
    order: Order = db.query(Order).filter(
        and_(Order.customer == new_customer.create_id, Order.payment_intent == new_customer.payment_intent)).first()

    if order is None:
        logger.error("Could not find order: {} {}".format(new_customer.create_id, new_customer.payment_intent))
        raise HTTPException(404)

    if customer is None:
        logger.error("Could not find customer: {}".format(new_customer.create_id))
        raise HTTPException(404)

    hashed_password = get_password_hash(new_customer.password)

    db.query(Customer).filter(Customer.id == new_customer.create_id).update({
        Customer.hashed_password: hashed_password,
        Customer.last_updated: datetime.now()
    })

    db.commit()

    return


@router.post("/update")
async def update_user_account(update_customer: UpdateCustomerPayload,
                              current_customer: Customer = Depends(get_current_customer),
                              db: Session = Depends(get_db)):
    verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.email == current_customer.email).first()
    if verified_sign_up is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not verified.")
    changes = {}
    # build changes dictionary
    if update_customer.first_name and update_customer.first_name != current_customer.first_name:
        changes['first_name'] = update_customer.first_name
    if update_customer.last_name and update_customer.last_name != current_customer.last_name:
        changes['last_name'] = update_customer.last_name
    if update_customer.email and update_customer.email != current_customer.email:
        # if email changes, send another verification email
        changes['email'] = update_customer.email
        changes['verified'] = False
        # add to unverified table, remove from verified table
        db.add(
            UnverifiedSignUp(
                email=update_customer.email,
                signup_date=datetime.now(),
                signup_from="CHANGE_EMAIL",
                zipcode=verified_sign_up.zipcode,
                verification_code=verified_sign_up.verification_code,
            )
        )
        db.delete(verified_sign_up)
        send_verify_email_best_effort(update_customer.email, verified_sign_up.verification_code)

    db.query(Customer).filter(Customer.email == current_customer.email).update(changes)
    db.commit()


@router.post("/change-password")
async def change_password(change_password_payload: ChangePasswordPayload,
                          current_customer: Customer = Depends(get_current_customer),
                          db: Session = Depends(get_db)):
    if not verify_password(change_password_payload.old_password, current_customer.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    new_password_hash: str = get_password_hash(change_password_payload.new_password)
    db.query(Customer).filter(Customer.email == current_customer.email).update({'hashed_password': new_password_hash})
    db.commit()
    # return new access token
    access_token = create_access_token(data={"sub": current_customer.email})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/initiate-reset-password")
async def initiate_reset_password(email: str, db: Session = Depends(get_db)):
    customer: Customer = db.query(Customer).filter(Customer.email == email).first()
    if customer is None or not customer.verified:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    reset_code: str = ''.join(random.choices(string.ascii_letters + string.digits, k=50))

    db.add(
        ResetPassword(
            email=customer.email,
            reset_code=reset_code,
            reset_date=datetime.now(),
            reset_complete=False
        )
    )
    db.commit()

    # send email with link to reset password
    send_reset_password_email_best_effort(customer.email, reset_code)


@router.post("/is-reset-password-allowed")
async def is_reset_password_allowed(reset_code: str, db: Session = Depends(get_db)) -> JSONResponse:
    now = datetime.now()
    reset_password: ResetPassword = db.query(ResetPassword).filter(ResetPassword.reset_code == reset_code).first()
    if reset_password is None:
        return JSONResponse(content=jsonable_encoder({
            "status": -1,
            "message": "Unknown reset request"
        }))
    time_since_password_requested = now - reset_password.reset_date
    if time_since_password_requested.total_seconds() > 1 * 60 * 60:
        return JSONResponse(content=jsonable_encoder({
            "status": -2,
            "message": "Reset request expired"
        }))
    return JSONResponse(content=jsonable_encoder({
        "status": 0,
        "email": reset_password.email,
        "message": "Reset allowed"
    }))


@router.post("/complete-reset-password")
async def complete_reset_password(reset_password: ResetPasswordPayload, db: Session = Depends(get_db)):
    reset_password_entry: ResetPassword = db.query(ResetPassword).filter(
        ResetPassword.reset_code == reset_password.reset_code).first()

    if reset_password_entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unrecognized password reset request.")

    customer: Customer = db.query(Customer).filter(Customer.email == reset_password_entry.email).first()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unrecognized customer.")

    hashed_password: str = get_password_hash(reset_password.new_password)
    db.query(Customer).filter(Customer.email == reset_password_entry.email).update({'hashed_password': hashed_password})
    db.query(ResetPassword).filter(ResetPassword.reset_code == reset_password.reset_code).update(
        {'reset_complete': True})
    db.commit()
    send_reset_password_complete_email_best_effort(customer.email, customer.first_name)


@router.get("/get_customer_from_intent")
async def get_customer_from_intent(create_id: int, payment_intent: str, db: Session = Depends(get_db)):
    customer: Customer = db.query(Customer).filter(Customer.id == create_id).first()
    order: Order = db.query(Order).filter(
        and_(Order.customer == create_id, Order.payment_intent == payment_intent)).first()

    if order is None:
        logger.error("Could not find order: {} {}".format(create_id, payment_intent))
        raise HTTPException(404)

    if customer is None:
        logger.error("Could not find customer: {}".format(create_id))
        raise HTTPException(404)

    return JSONResponse(content=jsonable_encoder({"email": customer.email}))


def create_welcome_promo_if_applicable(verification_code: str, db: Session):
    existing_promo_code = db.query(PromoCode).filter(
        PromoCode.redeemable_by_verification_code == verification_code).first()
    if existing_promo_code is not None:
        logger.info(
            "Ignoring welcome promo code creation because user already has a promo code: {}".format(verification_code))
        return

    db.add(
        PromoCode(
            promo_code_name="WELCOME15",
            created_on=datetime.now(),
            number_times_redeemed=0,
            stripe_promo_code_id=settings.stripe_welcome_promo_code_id,
            percent_off=15.0,
            redeemable_by_verification_code=verification_code
        )
    )

    return
