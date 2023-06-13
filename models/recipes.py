from sqlalchemy import Column, Integer, String, DateTime, Date, JSON

from models.base import Base


class RecipeContributor(Base):
    __tablename__ = "recipe_contributors"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    join_date = Column(DateTime)


class Recipe(Base):
    __tablename__ = "recipes"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    created_date = Column(DateTime)
    description = Column(String(1000))
    image_url = Column(String(10_000))
    recipe_contributor_id = Column(Integer)  # ForeignKey("recipe_contributors.id")
    prep_time_minutes = Column(Integer)
    cook_time_minutes = Column(Integer)


class StarredRecipe(Base):
    __tablename__ = "starred_recipes"
    id = Column(Integer, primary_key=True)
    starred_date = Column(DateTime)
    recipe_id = Column(Integer)  # ForeignKey("recipes.id")
    verified_sign_up_id = Column(Integer)  # ForeignKey("verified_sign_ups.id")


class RecipeSchedule(Base):
    __tablename__ = "recipe_schedules"
    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer)  # ForeignKey("recipes.id")
    schedule_start_date = Column(Date)


class InYourKitchen(Base):
    __tablename__ = "in_your_kitchen"
    id = Column(Integer, primary_key=True)
    name = Column(String(1000))


class Ingredient(Base):
    __tablename__ = "ingredients"
    id = Column(Integer, primary_key=True)
    name = Column(String(1000))
    description = Column(String(1000))
    category = Column(String(100))


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer)  # ForeignKey("recipes.id")
    ingredient_id = Column(Integer)  # ForeignKey("ingredients.id")
    quantity = Column(Integer)
    unit = Column(String(100))


class RecipeInYourKitchen(Base):
    __tablename__ = "recipe_in_your_kitchen"
    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer)  # ForeignKey("recipes.id")
    in_your_kitchen_id = Column(Integer)  # ForeignKey("in_your_kitchen.id")
    or_ids = Column(JSON)  # list<ForeignKey("in_your_kitchen.id")> of other similar items


class RecipeStep(Base):
    __tablename__ = "recipe_steps"
    id = Column(Integer, primary_key=True)
    step_number = Column(Integer)
    recipe_id = Column(Integer)  # ForeignKey("recipes.id")
    title = Column(String(1000))
    instructions = Column(JSON)  # list<string> of instructions
    tips = Column(JSON)  # list<string> of tips
    chefs_hats = Column(JSON)  # list<string> of chefs hat
    ingredients = Column(JSON)  # list<ForeignKey("ingredients.id")> of ingredients needed in this step
    in_your_kitchens = Column(
        JSON)  # list<ForeignKey("in_your_kitchen.id")> of items needed in this step that are not provided in the box
    gif_url = Column(String(10_000))
