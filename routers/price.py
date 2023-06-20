import logging
from functools import reduce
from typing import List, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.price import RecipeServingPrice
from dependencies.database import get_db
from dependencies.stripe_utils import create_stripe_product
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
        print(price)
        recipe = recipes[price.recipe_name]

        stripe_product = create_stripe_product(recipe.name, recipe.description, recipe.image_url, price.serving_size,
                                               price.price)
        recipe_prices.append(
            RecipePrice(recipe_id=recipe.id, serving_size=price.serving_size, price=price.price,
                        stripe_product_id=stripe_product["id"], stripe_price_id=stripe_product["default_price"]))

    db.add_all(recipe_prices)
    db.commit()

