import logging
from datetime import datetime
from functools import reduce
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.price import RecipeServingPrice
from config import Settings
from dependencies.database import get_db
from dependencies.stripe_utils import create_stripe_product, create_promo_code_from_coupon, find_promo_code_id
from emails.base import send_email, InvitationEmail
from models.customers import Customer
from models.orders import PromoCode
from models.recipes import Recipe, RecipePrice
from models.signups import VerifiedSignUp, DeliverableZipcode
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
    try:
        create_promo_code_from_coupon(stripe_coupon_id, customer_facing_code)
        promo_code = find_promo_code_id(customer_facing_code)
        if promo_code is None:
            raise HTTPException(status_code=400, detail="Unable to find promo code.")

        if not promo_code.active:
            raise HTTPException(status_code=400, detail="Created promo code is not active.")

        db.add(PromoCode(
            promo_code_name=promo_code.code,
            created_on=datetime.fromtimestamp(promo_code.created),
            number_times_redeemed=0,
            stripe_promo_code_id=promo_code.id,
            amount_off=to_dollars(promo_code.coupon.amount_off),
            percent_off=promo_code.coupon.percent_off,
            redeemable_by_verification_code=redeemable_by
        ))

        db.commit()
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=400, detail="Invalid stripe coupon id {}".format(stripe_coupon_id))


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


def to_dollars(cents):
    if cents is not None:
        return round(cents / 100.0, 2)
    return None


def to_promo_amount_string(promo_code: PromoCode) -> str:
    if promo_code.amount_off is not None:
        return "${:.2f}".format(promo_code.amount_off)
    elif promo_code.percent_off is not None:
        return "{}%".format(int(promo_code.percent_off))
