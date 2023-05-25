import logging
from datetime import datetime
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from api.recipes import CandidateRecipe, StarRecipe
from dependencies.database import get_db
from dependencies.events import emit_event
from models.recipes import Recipe, RecipeContributor, StarredRecipe, RecipeSchedule
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
            recipe_contributor_id=contributor.id
        )

    db.add_all(list(recipes_to_add.values()))
    db.commit()
    return


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
