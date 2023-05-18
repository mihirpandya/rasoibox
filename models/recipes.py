from sqlalchemy import Column, Integer, String, DateTime, Date

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
    recipe_contributor_id = Column(Integer)  # ForeignKey("recipe_contributors.id"))


class StarredRecipe(Base):
    __tablename__ = "starred_recipes"
    id = Column(Integer, primary_key=True)
    starred_date = Column(DateTime)
    recipe_id = Column(Integer)  # ForeignKey("recipes.id"))
    verified_sign_up_id = Column(Integer)  # ForeignKey("verified_sign_ups.id"))


class RecipeSchedule(Base):
    __tablename__ = "recipe_schedules"
    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer)  # ForeignKey("recipes.id"))
    schedule_start_date = Column(Date)
