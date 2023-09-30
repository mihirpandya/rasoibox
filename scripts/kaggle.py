import csv
from functools import reduce
from typing import List, Dict, Optional, Any

INGREDIENTS = "TranslatedIngredients"
RECIPE_NAME = "TranslatedRecipeName"
COURSE = "Course"

IN_MEMORY_DATASET: List[Dict[str, str]] = []
INGREDIENTS_COUNT: Dict[str, int] = {}
HD: Dict[str, int] = {}
SCORES: Dict[str, Any] = {}


def get_score(name):
    return SCORES[name]


def top_n_specialty_recipes(n=1) -> List[str]:
    sorted_recipes = list(SCORES.keys())
    sorted_recipes.sort(key=get_score, reverse=True)
    return sorted_recipes[0:n]


def sort_recipes_by_specialty(freq_threshold: int):
    for recipe in IN_MEMORY_DATASET:
        if recipe[COURSE].lower() != "vegetarian":
            raw_ingredients: List[str] = recipe[INGREDIENTS].split(',')
            SCORES[recipe[RECIPE_NAME]] = {
                "score": compute_specialty_score(raw_ingredients, freq_threshold),
                "ingredients": raw_ingredients
            }


def compute_specialty_score(raw_ingredients: List[str], freq_threshold: int) -> float:
    score = 0.0
    for ingredient in raw_ingredients:
        ingredient_name: Optional[str] = get_ingredient_name(ingredient)
        if ingredient_name:
            if ingredient_name in HD:
                ingredient_freq = HD[ingredient_name]
                if ingredient_freq > freq_threshold:
                    score += 1.0 / float(ingredient_freq)
    return score


def process_raw_kaggle_dataset(path_to_csv):
    global HD
    with open(path_to_csv, 'r') as kaggle_dataset:
        reader = csv.DictReader(kaggle_dataset)
        for row in reader:
            IN_MEMORY_DATASET.append(row)

    for recipe in IN_MEMORY_DATASET:
        ingredients: List[str] = recipe[INGREDIENTS].split(",")
        for ingredient in ingredients:
            ingredient_name: Optional[str] = get_ingredient_name(ingredient)
            if ingredient_name:
                if ingredient_name in INGREDIENTS_COUNT:
                    INGREDIENTS_COUNT[ingredient_name] += 1
                else:
                    INGREDIENTS_COUNT[ingredient_name] = 1
            else:
                print("No valid ingredient name: {}".format(ingredient))

    HD = reduce(lambda d1, d2: {**d1, **d2},
                [{x: INGREDIENTS_COUNT[x]} for x in INGREDIENTS_COUNT.keys() if INGREDIENTS_COUNT[x] > 1], {})

    return


def get_ingredient_name(ingredient: str) -> Optional[str]:
    space_separated = ingredient.split(' ')
    name = []
    for word in space_separated:
        if len(word) > 0:
            if word[0].isupper():
                name.append(word.strip())
            # name.append(word.strip())
        else:
            print("Ignoring word: {}".format(word))
    if len(name) > 0:
        return ' '.join(name)
    else:
        return None
