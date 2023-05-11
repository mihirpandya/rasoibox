from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from models.base import Base


class RecipeContributor(Base):
    __tablename__ = "recipe_contributors"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    join_date = Column(DateTime)

    recipes = relationship("Recipe", back_populates="contributor")


class Recipe(Base):
    __tablename__ = "recipes"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    created_date = Column(DateTime)
    description = Column(String(1000))
    image_url = Column(String(10_000))
    receipe_contributor_id = Column(Integer, ForeignKey("recipe_contributor.id"))

    recipe_contributor = relationship("RecipeContributor", back_populates="recipes")
    stars = relationship("StarredRecipe", back_populates="recipe")


class StarredRecipe(Base):
    __tablename__ = "starred_recipes"
    id = Column(Integer, primary_key=True)
    starred_date = Column(DateTime)
    recipe_id = Column(Integer, ForeignKey("recipe.id"))
    verified_sign_up_id = Column(Integer, ForeignKey("verified_sign_ups.id"))

    recipe = relationship("Recipe", back_populates="stars")
    starred_by = relationship("VerifiedSignUp", back_populates="starred_recipes")
