from typing import List, Optional

from pydantic import BaseModel


class Quantity(BaseModel):
    amount: float
    serving_size: int

    class Config:
        orm_mode = True


class Ingredient(BaseModel):
    name: str
    quantities: List[Quantity]
    unit: str

    class Config:
        orm_mode = True


class InYourKitchen(BaseModel):
    name: str
    or_: List[str]

    class Config:
        orm_mode = True


class RecipeMetadata(BaseModel):
    recipe_id: int
    recipe_name: str
    ingredients: List[Ingredient]
    in_your_kitchens: List[InYourKitchen]


class CandidateRecipe(BaseModel):
    contributor_name: str
    recipe_name: str
    description: str
    image_url: str
    prep_time_minutes: int
    cook_time_minutes: int

    class Config:
        orm_mode = True


class StarRecipe(BaseModel):
    verification_code: str
    recipe_id: int

    class Config:
        orm_mode = True


class RecipeStep(BaseModel):
    step_number: int
    title: str
    instructions: List[str]
    tips: List[str]
    chefs_hats: List[str]
    ingredients: List[str]
    in_your_kitchen: List[str]
    gif_url: Optional[List[str]]
