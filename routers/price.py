import logging
from datetime import datetime
from functools import reduce
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

import models.invitations
from api.price import RecipeServingPrice, Invitation
from config import Settings
from dependencies.customers import get_current_customer
from dependencies.database import get_db
from dependencies.referral_utils import create_stripe_promo_code, to_promo_amount_string, generate_promo_code
from dependencies.signup import generate_verification_code
from dependencies.stripe_utils import create_stripe_product
from emails.base import send_email, InvitationEmail
from models.customers import Customer
from models.orders import PromoCode
from models.recipes import Recipe, RecipePrice
from models.signups import VerifiedSignUp, DeliverableZipcode, UnverifiedSignUp
from routers.signup import jinjaEnv, smtp_server

logger = logging.getLogger("rasoibox")

router = APIRouter(
    prefix="/api/recipe_prices",
    tags=["recipe_prices"]
)

settings: Settings = Settings()


def send_invitation_email_best_effort(email: str, promo_code: str, promo_amount: str):
    url_base: str = settings.frontend_url_base[0:-1] if settings.frontend_url_base.endswith(
        "/") else settings.frontend_url_base

    invitation_email: InvitationEmail = InvitationEmail(
        url_base=url_base,
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


def is_new_user(email: str, db: Session) -> bool:
    verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(VerifiedSignUp.email == email).first()
    unverified_sign_up: UnverifiedSignUp = db.query(UnverifiedSignUp).filter(UnverifiedSignUp.email == email).first()
    customer: Customer = db.query(Customer).filter(Customer.email == email).first()
    invitation: Invitation = db.query(Invitation).filter(Invitation.email == email).first()
    return verified_sign_up is None and unverified_sign_up is None and customer is None and invitation is None


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
    send_invitation_email_best_effort(verified_sign_up.email, promo_code.promo_code_name, promo_amount)


@router.post("/initiate_invitation")
async def initiate_invitation(invitation: Invitation, current_customer: Customer = Depends(get_current_customer),
                              db: Session = Depends(get_db)):
    now = datetime.now()
    verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.email == current_customer.email).first()

    if verified_sign_up is None:
        raise HTTPException(status_code=404, detail="Unverified user.")

    # make sure this is a new user
    new_user: bool = is_new_user(invitation.email, db)
    if new_user is False:
        return JSONResponse(content=jsonable_encoder({"status": 1, "message": "Invited user already exists."}))

    # make sure user is in a deliverable zip code
    deliverable_zipcode: DeliverableZipcode = db.query(DeliverableZipcode).filter(
        DeliverableZipcode.zipcode == invitation.zipcode).first()

    if deliverable_zipcode is None or deliverable_zipcode.delivery_start_date > now:
        return JSONResponse(
            content=jsonable_encoder({"status": 2, "message": "Invited user not in deliverable zip code."}))

    # generate a verification code for invited user
    verification_code_for_invited_user: str = generate_verification_code()

    # generate promo code for invited user
    promo_code_for_invited_user: str = generate_promo_code(current_customer.first_name)

    # create stripe promo code
    promo_code: PromoCode = create_stripe_promo_code(settings.stripe_referral_coupon_id, promo_code_for_invited_user,
                                                     verification_code_for_invited_user, db)

    # create entry in UnverifiedSignUp table
    db.add(
        UnverifiedSignUp(
            email=invitation.email,
            signup_date=now,
            signup_from="INVITATION",
            zipcode=invitation.zipcode,
            verification_code=verification_code_for_invited_user,
        )
    )
    # create entry in invitation table with invitation status as "INVITED"
    db.add(models.invitations.Invitation(
        referred_by_customer_id=current_customer.id,
        email=invitation.email,
        verification_code=verification_code_for_invited_user,
        invitation_status=models.invitations.InvitationStatusEnum.INVITED
    ))

    db.commit()

    # send invitation email with promo code
    send_invitation_email_best_effort(invitation.email, promo_code.promo_code_name, to_promo_amount_string(promo_code))


@router.post("/complete_invitation")
async def complete_invitation(current_customer: Customer = Depends(get_current_customer),
                              db: Session = Depends(get_db)):
    verified_sign_up: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.email == current_customer.email).first()

    if verified_sign_up is None:
        raise HTTPException(status_code=404, detail="Unverified user")

    # check user has placed at least one order with payment_status marked as COMPLETED
    # find customer that referred current_customer in invitation table with invitation status as "INVITED"
    # return if no such entry
    # generate promo code for customer that referred current_customer
    # send email with promo code
    # mark invitation status as "COMPLETED"
