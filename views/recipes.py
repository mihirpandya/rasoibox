from sqladmin import ModelView

from models.recipes import RecipeContributor, StarredRecipe, Recipe


class RecipeContributorAdmin(ModelView, model=RecipeContributor):
    column_list = [
        RecipeContributor.id,
        RecipeContributor.name,
        RecipeContributor.join_date
    ]


class RecipeAdmin(ModelView, model=Recipe):
    column_list = [
        Recipe.id,
        Recipe.name,
        Recipe.created_date,
        Recipe.description,
        Recipe.image_url,
        Recipe.recipe_contributor_id
    ]


class StarredRecipeAdmin(ModelView, model=StarredRecipe):
    column_list = [
        StarredRecipe.id,
        StarredRecipe.starred_date,
        StarredRecipe.recipe_id,
        StarredRecipe.verified_sign_up_id
    ]
