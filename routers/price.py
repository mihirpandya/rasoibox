import logging
from datetime import datetime
from functools import reduce
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.price import RecipeServingPrice
from dependencies.database import get_db
from dependencies.stripe_utils import create_stripe_product, create_promo_code_from_coupon, find_promo_code_id
from models.orders import PromoCode
from models.recipes import Recipe, RecipePrice

logger = logging.getLogger("rasoibox")

router = APIRouter(
    prefix="/api/recipe_prices",
    tags=["recipe_prices"]
)


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
            amount_off=promo_code.amount_off,
            percent_off=promo_code.percent_off,
            redeemable_by_verification_code=redeemable_by
        ))

        db.commit()
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=400, detail="Invalid stripe coupon id {}".format(stripe_coupon_id))
