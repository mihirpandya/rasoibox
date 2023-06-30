from sqladmin import ModelView

from models.recipes import RecipeContributor, StarredRecipe, Recipe, RecipeSchedule, InYourKitchen, Ingredient, \
    RecipeIngredient, RecipeInYourKitchen, RecipeStep, RecipePrice


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
        Recipe.recipe_contributor_id,
        Recipe.prep_time_minutes,
        Recipe.cook_time_minutes,
        Recipe.tags,
    ]


class StarredRecipeAdmin(ModelView, model=StarredRecipe):
    column_list = [
        StarredRecipe.id,
        StarredRecipe.starred_date,
        StarredRecipe.recipe_id,
        StarredRecipe.verified_sign_up_id
    ]


class RecipeScheduleAdmin(ModelView, model=RecipeSchedule):
    column_list = [
        RecipeSchedule.id,
        RecipeSchedule.recipe_id,
        RecipeSchedule.schedule_start_date
    ]

    column_sortable_list = [RecipeSchedule.schedule_start_date]


class InYourKitchenAdmin(ModelView, model=InYourKitchen):
    column_list = [
        InYourKitchen.id,
        InYourKitchen.name
    ]

    column_searchable_list = [InYourKitchen.name]


class IngredientsAdmin(ModelView, model=Ingredient):
    column_list = [
        Ingredient.id,
        Ingredient.name,
        Ingredient.description
    ]

    column_searchable_list = [Ingredient.name]
    column_sortable_list = [Ingredient.name]


class RecipeIngredientsAdmin(ModelView, model=RecipeIngredient):
    column_list = [
        RecipeIngredient.id,
        RecipeIngredient.recipe_id,
        RecipeIngredient.ingredient_id,
        RecipeIngredient.quantity,
        RecipeIngredient.serving_size,
        RecipeIngredient.unit
    ]

    column_sortable_list = [RecipeIngredient.recipe_id]


class RecipeInYourKitchenAdmin(ModelView, model=RecipeInYourKitchen):
    column_list = [
        RecipeInYourKitchen.id,
        RecipeInYourKitchen.recipe_id,
        RecipeInYourKitchen.in_your_kitchen_id,
        RecipeInYourKitchen.or_ids
    ]

    column_sortable_list = [RecipeInYourKitchen.recipe_id]


class RecipeStepAdmin(ModelView, model=RecipeStep):
    column_list = [
        RecipeStep.id,
        RecipeStep.step_number,
        RecipeStep.recipe_id,
        RecipeStep.serving_size,
        RecipeStep.title,
        RecipeStep.instructions,
        RecipeStep.in_your_kitchens,
        RecipeStep.tips,
        RecipeStep.chefs_hats,
        RecipeStep.ingredients,
        RecipeStep.gif_url
    ]


class RecipePriceAdmin(ModelView, model=RecipePrice):
    column_list = [
        RecipePrice.id,
        RecipePrice.recipe_id,
        RecipePrice.serving_size,
        RecipePrice.price,
        RecipePrice.stripe_product_id,
        RecipePrice.stripe_price_id
    ]
