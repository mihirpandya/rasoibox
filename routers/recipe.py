import json
import logging
from datetime import datetime
from functools import reduce
from typing import List, Dict, Set

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

import api.recipes
import models.recipes
from api.recipes import CandidateRecipe, StarRecipe, RecipeStep, RecipeMetadata, Quantity
from dependencies.database import get_db
from dependencies.events import emit_event
from models.recipes import Recipe, RecipeContributor, StarredRecipe, RecipeSchedule, RecipeStep, \
    RecipeIngredient, InYourKitchen, RecipeInYourKitchen, Ingredient
from models.signups import VerifiedSignUp

logger = logging.getLogger("rasoibox")

router = APIRouter(
    prefix="/api/recipe",
    tags=["recipe"]
)


@router.post("/add")
async def add_recipes(recipes: List[CandidateRecipe], db: Session = Depends(get_db)):
    recipes_to_add: Dict[str, Recipe] = {}
    created_date = datetime.now()
    for recipe in recipes:
        contributor_name = recipe.contributor_name
        contributor = db.query(RecipeContributor).filter(RecipeContributor.name == contributor_name).first()
        if contributor is None:
            raise HTTPException(status_code=401, detail="Unrecognized contributor: {}.".format(contributor_name))

        existing_recipe = db.query(Recipe).filter(Recipe.name == recipe.recipe_name).first()
        if existing_recipe is not None:
            raise HTTPException(status_code=400, detail="Recipe with the same name already exists.")

        if recipe.recipe_name in recipes_to_add.keys():
            raise HTTPException(status_code=400, detail="Recipe names must be unique: {}.".format(recipe.recipe_name))

        recipes_to_add[recipe.recipe_name] = Recipe(
            name=recipe.recipe_name,
            created_date=created_date,
            description=recipe.description,
            image_url=recipe.image_url,
            recipe_contributor_id=contributor.id,
            prep_time_minutes=recipe.prep_time_minutes,
            cook_time_minutes=recipe.cook_time_minutes
        )

    db.add_all(list(recipes_to_add.values()))
    db.commit()
    return


@router.post("/add_recipe_metadata")
async def add_recipe_metadata(recipes: List[RecipeMetadata], db: Session = Depends(get_db)):
    recipes_ingredients_to_add: List[RecipeIngredient] = []
    recipes_in_your_kitchens_to_add: List[RecipeInYourKitchen] = []
    for recipe in recipes:
        existing_recipe: Recipe = db.query(Recipe).filter(Recipe.name == recipe.recipe_name).first()
        if existing_recipe is None:
            raise HTTPException(status_code=404, detail="Unknown recipe: {}.".format(recipe.recipe_name))

        ingredient_units: Dict[str, str] = reduce(lambda d1, d2: {**d1, **d2},
                                                  [{x.name: x.unit} for x in recipe.ingredients], {})
        ingredient_quantities: Dict[str, List[Quantity]] = reduce(lambda d1, d2: {**d1, **d2},
                                                                  [{x.name: x.quantities} for x in recipe.ingredients],
                                                                  {})
        ingredient_ids: Dict[str, int] = upsert_ingredient_ids([x.name for x in recipe.ingredients], db)

        for ingredient_name, ingredient_id in ingredient_ids.items():
            quantities: List[Quantity] = ingredient_quantities[ingredient_name]
            for quantity in quantities:
                recipes_ingredients_to_add.append(
                    RecipeIngredient(recipe_id=existing_recipe.id, ingredient_id=ingredient_id,
                                     quantity=quantity.amount, serving_size=quantity.serving_size,
                                     unit=ingredient_units[ingredient_name]))

        in_your_kitchen_or_ids: Dict[str, List[str]] = reduce(lambda d1, d2: {**d1, **d2},
                                                              [{x.name: x.or_} for x in recipe.in_your_kitchens], {})
        in_your_kitchen_ids: Dict[str, int] = upsert_in_your_kitchen_ids([x.name for x in recipe.in_your_kitchens], db)
        for in_your_kitchen_name, in_your_kitchen_id in in_your_kitchen_ids.items():
            or_in_your_kitchen_ids: Dict[str, int] = upsert_in_your_kitchen_ids(
                in_your_kitchen_or_ids[in_your_kitchen_name], db)
            recipes_in_your_kitchens_to_add.append(
                RecipeInYourKitchen(recipe_id=existing_recipe.id, in_your_kitchen_id=in_your_kitchen_id,
                                    or_ids=list(or_in_your_kitchen_ids.values()))
            )
    db.add_all(recipes_ingredients_to_add)
    db.add_all(recipes_in_your_kitchens_to_add)
    db.commit()
    return


@router.post("/add_recipe_steps")
async def add_recipe_steps(recipe_id: int, steps: List[api.recipes.RecipeStep], db: Session = Depends(get_db)):
    recipe: Recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if recipe is None:
        raise HTTPException(status_code=404, detail="Unknown recipe")
    all_steps: List[RecipeStep] = []
    unique_ingredient_ids = set()
    unique_in_your_kitchen_ids = set()
    for step in steps:
        ingredient_ids: List[int] = list(get_ingredient_ids(step.ingredients, db).values())
        in_your_kitchen_ids: List[int] = list(get_in_your_kitchen_ids(step.in_your_kitchen, db).values())
        unique_ingredient_ids.update(ingredient_ids)
        unique_in_your_kitchen_ids.update(in_your_kitchen_ids)
        all_steps.append(RecipeStep(
            step_number=step.step_number,
            recipe_id=recipe.id,
            title=step.title,
            instructions=json.dumps(step.instructions),
            tips=json.dumps(step.tips),
            chefs_hats=json.dumps(step.chefs_hats),
            ingredients=json.dumps(ingredient_ids),
            in_your_kitchens=json.dumps(in_your_kitchen_ids),
            gif_url=step.gif_url
        ))
    ingredients_to_update: List[RecipeIngredient] = get_ingredients_to_update(recipe_id, unique_ingredient_ids, db)
    in_your_kitchens_to_update: List[RecipeInYourKitchen] = get_in_your_kitchens_to_update(recipe_id,
                                                                                           unique_in_your_kitchen_ids,
                                                                                           db)
    db.add_all(all_steps)
    db.add_all(ingredients_to_update)
    db.add_all(in_your_kitchens_to_update)
    db.commit()


@router.get("/get")
async def get_recipe_by_name(name: str, db: Session = Depends(get_db)):
    recipe: Recipe = db.query(Recipe).filter(Recipe.name == name).first()
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    else:
        return {
            "recipe_id": recipe.id
        }


@router.get("/get_by_id")
async def get_recipe_by_id(id: int, db: Session = Depends(get_db)):
    recipe: Recipe = db.query(Recipe).filter(Recipe.id == id).first()
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    else:
        return {
            "recipe_name": recipe.name
        }


@router.get("/get_recipe_metadata")
async def get_recipe_metadata(name: str, db: Session = Depends(get_db)) -> RecipeMetadata:
    recipe: Recipe = db.query(Recipe).filter(Recipe.name == name).first()
    if recipe is None:
        raise HTTPException(status_code=404, detail="Unrecognized recipe: {}".format(name))
    recipe_ingredients: List[RecipeIngredient] = db.query(RecipeIngredient).filter(
        RecipeIngredient.recipe_id == recipe.id).all()
    recipe_in_your_kitchens: List[RecipeInYourKitchen] = db.query(RecipeInYourKitchen).filter(
        RecipeInYourKitchen.recipe_id == recipe.id).all()
    recipe_ingredients_ids = [x.ingredient_id for x in recipe_ingredients]
    recipe_in_your_kitchens_ids = [x.in_your_kitchen_id for x in recipe_in_your_kitchens]
    ingredients_to_units: Dict[int, str] = reduce(lambda d1, d2: {**d1, **d2},
                                                  [{x.ingredient_id: x.unit} for x in recipe_ingredients], {})
    ingredients_to_quantities: Dict[int, List[Quantity]] = \
        reduce(lambda d1, d2: {**d1, **d2},
               [{x.ingredient_id: [Quantity(amount=y.quantity,
                                            serving_size=y.serving_size)
                                   for y in recipe_ingredients if
                                   y.ingredient_id == x.ingredient_id]}
                for x in recipe_ingredients], {})
    in_your_kitchen_to_ors_ids: Dict[int, List[int]] = \
        reduce(lambda d1, d2: {**d1, **d2},
               [{x.in_your_kitchen_id: x.or_ids} for x in
                recipe_in_your_kitchens],
               {})
    ingredients: List[Ingredient] = db.query(Ingredient).filter(Ingredient.id.in_(recipe_ingredients_ids)).all()
    in_your_kitchens: List[InYourKitchen] = db.query(InYourKitchen).filter(
        InYourKitchen.id.in_(recipe_in_your_kitchens_ids)).all()

    ingredients_metadata: List[api.recipes.Ingredient] = \
        [api.recipes.Ingredient(name=ingredient.name, quantities=ingredients_to_quantities[ingredient.id],
                                unit=ingredients_to_units[ingredient.id]) for ingredient in ingredients]

    in_your_kitchens_metadata: List[api.recipes.InYourKitchen] = []
    for in_your_kitchen in in_your_kitchens:
        or_names: List[str] = [x.name for x in db.query(InYourKitchen).filter(
            InYourKitchen.id.in_(in_your_kitchen_to_ors_ids[in_your_kitchen.id])).all()]
        in_your_kitchens_metadata.append(
            api.recipes.InYourKitchen(
                name=in_your_kitchen.name,
                or_=or_names
            )
        )

    return RecipeMetadata(
        recipe_name=recipe.name,
        ingredients=ingredients_metadata,
        in_your_kitchens=in_your_kitchens_metadata
    )


@router.get("/get_recipe_steps")
async def get_recipe_steps(name: str, db: Session = Depends(get_db)) -> List[api.recipes.RecipeStep]:
    recipe: Recipe = db.query(Recipe).filter(Recipe.name == name).first()
    if recipe is None:
        raise HTTPException(status_code=404, detail="Unrecognized recipe: {}".format(name))
    recipe_steps: List[models.recipes.RecipeStep] = db.query(models.recipes.RecipeStep).filter(
        models.recipes.RecipeStep.recipe_id == recipe.id).all()
    return [api.recipes.RecipeStep(
        step_number=x.step_number,
        title=x.title,
        instructions=json.loads(x.instructions),
        tips=json.loads(x.tips),
        chefs_hats=json.loads(x.chefs_hats),
        ingredients=[x.name for x in db.query(Ingredient).filter(Ingredient.id.in_(json.loads(x.ingredients))).all()],
        in_your_kitchen=[x.name for x in
                         db.query(InYourKitchen).filter(InYourKitchen.id.in_(json.loads(x.in_your_kitchens))).all()],
        gif_url=x.gif_url
    ) for x in recipe_steps]


@router.post("/star")
async def toggle_star_recipe(recipe_to_star: StarRecipe, db: Session = Depends(get_db)):
    star_date = datetime.now()
    recipe: Recipe = db.query(Recipe).filter(Recipe.id == recipe_to_star.recipe_id).first()
    starred_by: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.verification_code == recipe_to_star.verification_code).first()

    if recipe is None:
        raise HTTPException(status_code=404, detail="Unrecognized recipe id: {}.".format(recipe_to_star.recipe_id))

    if starred_by is None:
        raise HTTPException(status_code=401, detail="Unverified user.")

    existing_star: StarredRecipe = db.query(StarredRecipe).filter(and_(
        StarredRecipe.recipe_id == recipe.id, StarredRecipe.verified_sign_up_id == starred_by.id)).first()

    event_type: str
    if existing_star is None:
        event_type = "STAR"
        db.add(
            StarredRecipe(
                recipe_id=recipe.id,
                verified_sign_up_id=starred_by.id,
                starred_date=star_date
            )
        )
    else:
        event_type = "UNSTAR"
        db.delete(existing_star)

    db.commit()

    emit_event(db, event_type, star_date, recipe_to_star.verification_code, None)

    return


@router.get("/stars")
async def get_stars_for_user(id: str, db: Session = Depends(get_db)) -> JSONResponse:
    verified_user = db.query(VerifiedSignUp).filter(VerifiedSignUp.verification_code == id).first()
    if verified_user is None:
        raise HTTPException(status_code=401, detail="Unrecognized user.")

    starred_recipes: List[StarredRecipe] = db.query(StarredRecipe).filter(
        StarredRecipe.verified_sign_up_id == verified_user.id).all()
    result = []
    for starred_recipe in starred_recipes:
        recipe: Recipe = db.query(Recipe).filter(Recipe.id == starred_recipe.recipe_id).first()
        result.append(recipe.name)
    return JSONResponse(content=jsonable_encoder(result))


@router.get("/schedule")
async def get_recipe_schedule(id: str, db: Session = Depends(get_db)) -> JSONResponse:
    verified_user = db.query(VerifiedSignUp).filter(VerifiedSignUp.verification_code == id).first()
    if verified_user is None:
        raise HTTPException(status_code=401, detail="Unrecognized user.")
    result = {}
    recipe_schedule: List[RecipeSchedule] = db.query(RecipeSchedule).order_by(
        RecipeSchedule.schedule_start_date.asc()).all()
    starred_recipe_ids: List[int] = [x.recipe_id for x in db.query(StarredRecipe).filter(
        StarredRecipe.verified_sign_up_id == verified_user.id).all()]
    for item in recipe_schedule:
        recipe: Recipe = db.query(Recipe).filter(Recipe.id == item.recipe_id).first()
        if recipe is None:
            logger.error("Schedule has invalid recipe_id: {} {}".format(item.id, item.recipe_id))
        else:
            if item.schedule_start_date not in result:
                result[item.schedule_start_date] = []
            result[item.schedule_start_date].append({
                "id": recipe.id,
                "name": recipe.name,
                "description": recipe.description,
                "image_url": recipe.image_url,
                "starred": True if recipe.id in starred_recipe_ids else False
            })

    return JSONResponse(content=jsonable_encoder(result))


def get_ingredients_to_update(recipe_id: int, unique_ingredient_ids: Set[int], db: Session) -> List[RecipeIngredient]:
    existing_recipe_ingredients: List[RecipeIngredient] = db.query(RecipeIngredient).filter(
        RecipeIngredient.recipe_id == recipe_id).all()
    existing_recipe_ingredients_ids = [x.ingredient_id for x in existing_recipe_ingredients]
    ingredients_to_update: List[RecipeIngredient] = []
    for unique_ingredient in unique_ingredient_ids:
        if unique_ingredient not in existing_recipe_ingredients_ids:
            ingredients_to_update.append(RecipeIngredient(recipe_id=recipe_id, ingredient_id=unique_ingredient))
    return ingredients_to_update


def get_in_your_kitchens_to_update(recipe_id: int, unique_in_your_kitchen_ids: Set[int], db: Session) \
        -> List[RecipeInYourKitchen]:
    existing_recipe_in_your_kitchens: List[RecipeInYourKitchen] = db.query(RecipeInYourKitchen).filter(
        RecipeInYourKitchen.recipe_id == recipe_id).all()
    existing_recipe_in_your_kitchen_ids = [x.in_your_kitchen_id for x in existing_recipe_in_your_kitchens]
    in_your_kitchens_to_update: List[RecipeIngredient] = []
    for unique_in_your_kitchen in unique_in_your_kitchen_ids:
        if unique_in_your_kitchen not in existing_recipe_in_your_kitchen_ids:
            in_your_kitchens_to_update.append(
                RecipeInYourKitchen(recipe_id=recipe_id, in_your_kitchen_id=unique_in_your_kitchen))
    return in_your_kitchens_to_update


def get_ingredient_ids(ingredients: List[str], db: Session) -> Dict[str, int]:
    ingredient_ids: Dict[str, int] = {}
    for ingredient_name in ingredients:
        ingredient: Ingredient = db.query(Ingredient).filter(Ingredient.name == ingredient_name).first()
        if ingredient is None:
            raise HTTPException(status_code=400, detail="Invalid ingredient {}".format(ingredient_name))
        ingredient_ids[ingredient_name] = ingredient.id
    return ingredient_ids


def get_in_your_kitchen_ids(in_your_kitchens: List[str], db: Session) -> Dict[str, int]:
    in_your_kitchen_ids: Dict[str, int] = {}
    for in_your_kitchen_name in in_your_kitchens:
        in_your_kitchen: InYourKitchen = db.query(InYourKitchen).filter(
            InYourKitchen.name == in_your_kitchen_name).first()
        if in_your_kitchen is None:
            raise HTTPException(status_code=400, detail="Invalid in-your-kitchen item {}".format(in_your_kitchen_name))
        in_your_kitchen_ids[in_your_kitchen_name] = in_your_kitchen.id
    return in_your_kitchen_ids


def upsert_ingredient_ids(ingredients: List[str], db: Session) -> Dict[str, int]:
    existing_ingredients: List[str] = [x.name for x in
                                       db.query(Ingredient).filter(Ingredient.name.in_(ingredients)).all()]
    ingredients_to_insert = []
    for ingredient in ingredients:
        if ingredient not in existing_ingredients:
            ingredients_to_insert.append(Ingredient(name=ingredient))
    db.add_all(ingredients_to_insert)
    db.commit()
    return reduce(lambda d1, d2: {**d1, **d2},
                  [{x.name: x.id} for x in db.query(Ingredient).filter(Ingredient.name.in_(ingredients)).all()], {})


def upsert_in_your_kitchen_ids(in_your_kitchens: List[str], db: Session) -> Dict[str, int]:
    existing_in_your_kitchens: List[str] = [x.name for x in
                                            db.query(InYourKitchen).filter(
                                                InYourKitchen.name.in_(in_your_kitchens)).all()]
    in_your_kitchens_to_insert = []
    for in_your_kitchen in in_your_kitchens:
        if in_your_kitchen not in existing_in_your_kitchens:
            in_your_kitchens_to_insert.append(InYourKitchen(name=in_your_kitchen))
    db.add_all(in_your_kitchens_to_insert)
    db.commit()
    return reduce(lambda d1, d2: {**d1, **d2},
                  [{x.name: x.id} for x in
                   db.query(InYourKitchen).filter(InYourKitchen.name.in_(in_your_kitchens)).all()], {})
