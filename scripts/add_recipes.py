import csv

import requests


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
