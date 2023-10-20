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
from api.cooking import FinishCookingPayload
from api.event import SiteEvent
from api.recipes import CandidateRecipe, StarRecipe, RecipeStep, RecipeMetadata, Quantity
from dependencies.customers import get_current_customer
from dependencies.database import get_db
from dependencies.events import emit_event
from models.cooking import CookingHistory
from models.customers import Customer
from models.event import RecipeEvent
from models.orders import Order
from models.recipes import Recipe, RecipeContributor, StarredRecipe, RecipeSchedule, RecipeStep, \
    RecipeIngredient, InYourKitchen, RecipeInYourKitchen, Ingredient
from models.signups import VerifiedSignUp

logger = logging.getLogger("rasoibox")

router = APIRouter(
    prefix="/api/cooking",
    tags=["cooking"]
)


@router.post("/finish_cooking")
async def finish_cooking(cooking_payload: FinishCookingPayload,
                         current_customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)):
    order: Order = db.query(Order).filter(
        and_(Order.user_facing_order_id == cooking_payload.order_id, Order.customer == current_customer.id)).first()

    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")

    if str(cooking_payload.recipe_id) not in json.loads(order.recipes):
        raise HTTPException(status_code=404, detail="Recipe not found in order.")

    cooking_history: CookingHistory = db.query(CookingHistory).filter(
        and_(CookingHistory.recipe_id == cooking_payload.recipe_id, CookingHistory.order_id == cooking_payload.order_id,
             CookingHistory.customer_id == current_customer.id)).first()

    if cooking_history is None:
        db.add(
            CookingHistory(
                customer_id=current_customer.id,
                order_id=order.user_facing_order_id,
                recipe_id=cooking_payload.recipe_id,
                cook_date=cooking_payload.cook_date
            )
        )

        db.commit()


@router.get("/can_finish_cooking")
async def can_finish_cooking(recipe_id: int, order_number: str,
                             current_customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)):
    order: Order = db.query(Order).filter(
        and_(Order.user_facing_order_id == order_number, Order.customer == current_customer.id)).first()

    if order is None:
        return JSONResponse(content=jsonable_encoder({"can_finish_cooking": False}))

    if str(recipe_id) not in json.loads(order.recipes):
        return JSONResponse(content=jsonable_encoder({"can_finish_cooking": False}))

    cooking_history = None

    # cooking_history: CookingHistory = db.query(CookingHistory).filter(
    #     and_(CookingHistory.recipe_id == recipe_id, CookingHistory.order_id == order_number,
    #          CookingHistory.customer_id == current_customer.id)).first()

    return JSONResponse(content=jsonable_encoder({"can_finish_cooking": cooking_history is None}))
