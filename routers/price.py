import logging
from datetime import datetime
from functools import reduce
from typing import List, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

import models.invitations
from api.price import RecipeServingPrice, Invitation, ReferredEmails
from config import Settings
from dependencies.customers import get_current_customer
from dependencies.database import get_db
from dependencies.referral_utils import create_stripe_promo_code, to_promo_amount_string, generate_promo_code
from dependencies.signup import generate_verification_code
from dependencies.stripe_utils import create_stripe_product
from emails.base import send_email
from emails.invitation import InvitationEmail
from emails.referral import ReferralEmail
from emails.referralauth import ReferralAuthEmail
from models.customers import Customer
from models.orders import PromoCode
from models.recipes import Recipe, RecipePrice
from models.signups import VerifiedSignUp, DeliverableZipcode, UnverifiedSignUp
from routers.signup import jinjaEnv, smtp_server, send_verify_email

logger = logging.getLogger("rasoibox")

router = APIRouter(
    prefix="/api/recipe_prices",
    tags=["recipe_prices"]
)

settings: Settings = Settings()


def send_auth_referral_email_best_effort(email: str, referrer_first_name: str, referrer_last_name: str,
                                         verification_code: str, promo_code: str, promo_amount: str):
    url_base: str = settings.frontend_url_base[0:-1] if settings.frontend_url_base.endswith(
        "/") else settings.frontend_url_base

    referral_email: ReferralAuthEmail = ReferralAuthEmail(
        url_base=url_base,
        first_name=referrer_first_name,
        last_name=referrer_last_name,
        verification_code=verification_code,
        promo_code=promo_code,
        promo_amount=promo_amount,
        to_email=email,
        from_email=settings.from_email
    )

    # send email best effort
    try:
        send_email(jinjaEnv, referral_email, smtp_server, settings.email, settings.email_app_password)
    except Exception:
        logger.exception("Failed to send email.")


def send_referral_email_best_effort(referred_email: str, referrer_email: str, referred_verification_code: str,
                                    promo_code: str, promo_amount: str):
    url_base: str = settings.frontend_url_base[0:-1] if settings.frontend_url_base.endswith(
        "/") else settings.frontend_url_base

    referral_email: ReferralEmail = ReferralEmail(
        url_base=url_base,
        referrer_email=referrer_email,
        verification_code=referred_verification_code,
        promo_code=promo_code,
        promo_amount=promo_amount,
        to_email=referred_email,
        from_email=settings.from_email
    )

    # send email best effort
    try:
        send_email(jinjaEnv, referral_email, smtp_server, settings.email, settings.email_app_password)
    except Exception:
        logger.exception("Failed to send email.")


def send_invitation_email_best_effort(email: str, verification_code: str, promo_code: str, promo_amount: str):
    url_base: str = settings.frontend_url_base[0:-1] if settings.frontend_url_base.endswith(
        "/") else settings.frontend_url_base

    invitation_email: InvitationEmail = InvitationEmail(
        url_base=url_base,
        verification_code=verification_code,
        promo_code=promo_code,
        promo_amount=promo_amount,
        to_email=email,
        from_email=settings.from_email
    )

    # send email best effort
    try:
        send_email(jinjaEnv, invitation_email, smtp_server, settings.email, settings.email_app_password)
    except Exception:
        logger.exception("Failed to send email.")


def get_verification_code_for_email(email: str, db: Session) -> Optional[str]:
    verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(VerifiedSignUp.email == email).first()
    if verified_sign_up is not None:
        return verified_sign_up.verification_code
    unverified_sign_up: UnverifiedSignUp = db.query(UnverifiedSignUp).filter(UnverifiedSignUp.email == email).first()
    if unverified_sign_up is not None:
        return unverified_sign_up.verification_code
    invitation: models.invitations.Invitation = db.query(models.invitations.Invitation).filter(
        models.invitations.Invitation.email == email).first()
    if invitation is not None:
        return invitation.referred_verification_code
    return None


@router.post("/add_prices")
async def add_prices(prices: List[RecipeServingPrice], db: Session = Depends(get_db)):
    unique_recipe_names = list(set([x.recipe_name for x in prices]))
    recipes: Dict[str, Recipe] = reduce(lambda d1, d2: {**d1, **d2}, [{x.name: x} for x in db.query(Recipe).filter(
        Recipe.name.in_(unique_recipe_names)).all()], {})
    recipe_prices: List[RecipePrice] = []
    for price in prices:
        recipe = recipes[price.recipe_name]

        stripe_product = create_stripe_product(recipe.name, recipe.description, recipe.image_url, price.serving_size,
                                               price.price)
        recipe_prices.append(
            RecipePrice(recipe_id=recipe.id, serving_size=price.serving_size, price=price.price,
                        stripe_product_id=stripe_product["id"], stripe_price_id=stripe_product["default_price"]))

    db.add_all(recipe_prices)
    db.commit()


@router.post("/create_promo_code")
async def create_promo_code(stripe_coupon_id: str, customer_facing_code: str, redeemable_by: str,
                            db: Session = Depends(get_db)):
    create_stripe_promo_code(stripe_coupon_id, customer_facing_code, redeemable_by, db)


@router.post("/invite_verified_user")
async def invite_verified_user(verification_code: str, db: Session = Depends(get_db)):
    now = datetime.now()
    verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.verification_code == verification_code).first()
    if verified_sign_up is None:
        raise HTTPException(status_code=404, detail="Unknown user")

    customer: Customer = db.query(Customer).filter(Customer.email == verified_sign_up.email).first()
    if customer is not None:
        raise HTTPException(status_code=404, detail="User has already created an account.")

    deliverable_zip_code: DeliverableZipcode = db.query(DeliverableZipcode).filter(
        DeliverableZipcode.zipcode == verified_sign_up.zipcode).first()

    if deliverable_zip_code is None or deliverable_zip_code.delivery_start_date > now:
        raise HTTPException(status_code=400, detail="Zipcode not deliverable")

    promo_code: PromoCode = db.query(PromoCode).filter(
        PromoCode.redeemable_by_verification_code == verification_code).first()

    if promo_code is None:
        raise HTTPException(status_code=400, detail="No promo code assigned to user")

    promo_amount: str = to_promo_amount_string(promo_code)
    send_invitation_email_best_effort(verified_sign_up.email, verified_sign_up.verification_code,
                                      promo_code.promo_code_name, promo_amount)


@router.post("/initiate_invitation_auth")
async def initiate_invitation_auth(referred_emails: ReferredEmails,
                                   current_customer: Customer = Depends(get_current_customer),
                                   db: Session = Depends(get_db)):
    verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.email == current_customer.email).first()

    if verified_sign_up is None:
        raise HTTPException(status_code=404, detail="Unverified user.")

    successes: List[str] = []
    failures: List[str] = []

    for referred_email in referred_emails.referred_emails:
        # make sure this is a new user
        new_user: bool = get_verification_code_for_email(referred_email, db) is None
        if new_user is False:
            failures.append(referred_email)
        else:
            try:
                # generate a verification code for invited user
                referred_verification_code: str = generate_verification_code()

                # generate promo code for invited user
                promo_code_for_invited_user: str = generate_promo_code(current_customer.first_name)

                # create stripe promo code
                promo_code: PromoCode = create_stripe_promo_code(settings.stripe_referral_coupon_id,
                                                                 promo_code_for_invited_user,
                                                                 referred_verification_code, db)

                # create entry in invitation table with invitation status as "INVITED"
                db.add(
                    models.invitations.Invitation(
                        email=referred_email,
                        referrer_verification_code=verified_sign_up.verification_code,
                        referred_verification_code=referred_verification_code,
                        invitation_status=models.invitations.InvitationStatusEnum.INVITED,
                        invited_on=datetime.now()
                    )
                )

                successes.append(referred_email)

                # send invitation email with promo code
                send_auth_referral_email_best_effort(referred_email, current_customer.first_name,
                                                     current_customer.last_name,
                                                     referred_verification_code, promo_code.promo_code_name,
                                                     to_promo_amount_string(promo_code))
            except Exception as e:
                logger.exception(e)
                failures.append(referred_email)

    db.commit()

    return JSONResponse(content=jsonable_encoder({"status": 1, "successes": successes, "failures": failures}))


@router.post("/initiate_invitation")
async def initiate_invitation(invitation: Invitation, db: Session = Depends(get_db)):
    now = datetime.now()
    referrer_verification_code: Optional[str] = get_verification_code_for_email(invitation.referrer_email, db)

    if referrer_verification_code is None:
        # brand new user; insert in unverified sign up
        referrer_verification_code = generate_verification_code()

        db.add(
            UnverifiedSignUp(
                email=invitation.referrer_email,
                signup_date=now,
                signup_from="REFERRER",
                verification_code=referrer_verification_code
            )
        )

        send_verify_email(invitation.referrer_email, referrer_verification_code)

    successes: List[str] = []
    failures: List[str] = []

    for referred_email in invitation.referred_emails.referred_emails:
        # make sure this is a new user
        new_user: bool = get_verification_code_for_email(referred_email, db) is None
        if new_user is False:
            failures.append(referred_email)
        else:
            try:
                # generate a verification code for invited user
                referred_verification_code: str = generate_verification_code()

                # generate promo code for invited user
                promo_code_for_invited_user: str = generate_promo_code("INVITE")

                # create stripe promo code
                promo_code: PromoCode = create_stripe_promo_code(settings.stripe_referral_coupon_id,
                                                                 promo_code_for_invited_user,
                                                                 referred_verification_code, db)

                # create entry in invitation table with invitation status as "INVITED"
                db.add(
                    models.invitations.Invitation(
                        email=referred_email,
                        referrer_verification_code=referrer_verification_code,
                        referred_verification_code=referred_verification_code,
                        invitation_status=models.invitations.InvitationStatusEnum.INVITED,
                        invited_on=datetime.now()
                    )
                )

                successes.append(referred_email)

                # send invitation email with promo code
                send_referral_email_best_effort(referred_email, invitation.referrer_email,
                                                referred_verification_code,
                                                promo_code.promo_code_name, to_promo_amount_string(promo_code))
            except Exception as e:
                logger.exception(e)
                failures.append(referred_email)

    db.commit()

    return JSONResponse(content=jsonable_encoder({"status": 1, "successes": successes, "failures": failures}))


@router.get("/get_eligible_invitees")
async def get_eligible_invitees(db: Session = Depends(get_db)):
    # invitees should be in verified sign up table but not in customer table
    # invitees should not have any redeemable promo codes
    # invitees should be in deliverable zipcodes
    all_deliverable_zipcodes: List[str] = [x.zipcode for x in db.query(DeliverableZipcode).all()]
    all_customers_emails: List[str] = [x.email for x in db.query(Customer).all()]
    redeemable_verification_codes: List[str] = [x.redeemable_by_verification_code for x in db.query(PromoCode).all()]
    verified_sign_ups: List[VerifiedSignUp] = db.query(VerifiedSignUp).filter(
        and_(VerifiedSignUp.zipcode.in_(all_deliverable_zipcodes),
             VerifiedSignUp.email.not_in(all_customers_emails),
             VerifiedSignUp.verification_code.not_in(redeemable_verification_codes))).all()

    return JSONResponse(content=jsonable_encoder([x.verification_code for x in verified_sign_ups]))
