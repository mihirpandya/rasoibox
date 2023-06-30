import csv

import requests
import yaml


def add_recipes(csv_file, url_base):
    url = url_base + "/api/recipe/add"
    payload = []
    with open(csv_file, "r") as data:
        for line in csv.DictReader(data):
            payload.append(
                {
                    "contributor_name": "Rasoi Box",
                    "recipe_name": line["Dish"],
                    "description": line["Description"],
                    "image_url": line["Image URL"]
                }
            )

    res = requests.post(url, json=payload)
    return res


def add_recipe_steps(yml_file, url_base, proceed=False):
    with open(yml_file, 'r') as file:
        recipe = yaml.safe_load(file)

    add_recipe_url = url_base + "/api/recipe/add"
    r = requests.post(add_recipe_url, json=[
        {
            "contributor_name": recipe['recipe_contributor_name'],
            "recipe_name": recipe['recipe_name'],
            "description": recipe['description'],
            "image_url": recipe['image_url'],
            "prep_time_minutes": recipe['prep_time_minutes'],
            "cook_time_minutes": recipe['cook_time_minutes']
        }
    ])

    if not r.ok:
        print("Failed to create recipe.")
        if not proceed:
            return r

    serving_size = recipe['serving_size']
    get_recipe_url = url_base + "/api/recipe/get?name=" + recipe['recipe_name']
    r = requests.get(get_recipe_url)
    recipe_id = r.json()['recipe_id']
    add_recipe_metadata_url = url_base + "/api/recipe/add_recipe_metadata"
    ingredients = [
        {"name": x['name'], "quantities": [{"amount": float(x['quantities'][0]['amount']), "serving_size": serving_size}],
         "unit": x['unit']} for x in recipe['ingredients']]
    in_your_kitchens = [{"name": x['name'], "or_": x["or"] if "or" in x else []} for x in recipe['in_your_kitchen']]
    payload = {
        "recipe_name": recipe['recipe_name'],
        "ingredients": ingredients,
        "in_your_kitchens": in_your_kitchens,
    }
    r = requests.post(add_recipe_metadata_url, json=[payload])
    if not r.ok:
        print("Failed to create recipe metadata.")
        return r

    add_recipe_steps_url = url_base + "/api/recipe/add_recipe_steps?recipe_id=" + str(
        recipe_id) + "&serving_size=" + str(serving_size)
    payload = [{
        "step_number": x['step_number'],
        "title": x['title'],
        "instructions": x['instructions'],
        "tips": x['tips'],
        "chefs_hats": x['chefs_hats'],
        "ingredients": x['ingredients'],
        "in_your_kitchen": x['in_your_kitchen'],
        "gif_url": x['gif_url'] if 'gif_url' in x else []
    } for x in recipe["steps"]]

    r = requests.post(add_recipe_steps_url, json=payload)
    return r


def get_recipe_metadata(url_base, recipe_name):
    return requests.get(url_base + '/api/recipe/get_recipe_metadata?name=' + recipe_name)


def get_recipe_steps(url_base, recipe_name):
    return requests.get(url_base + '/api/recipe/get_recipe_steps?name=' + recipe_name)
