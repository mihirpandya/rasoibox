from html.parser import HTMLParser

import requests


def is_valid_recipe_url(url: str) -> bool:
    return url.startswith("https://www.hellofresh.com/recipes/") and url not in ['https://www.hellofresh.com/recipes/',
                                                                                 'https://www.hellofresh.com/recipes/quick-meals',
                                                                                 'https://www.hellofresh.com/recipes/most-recent-recipes',
                                                                                 'https://www.hellofresh.com/recipes/most-popular-recipes',
                                                                                 'https://www.hellofresh.com/recipes/easy-recipes']


class HelloFreshIndexParser(HTMLParser):
    _seeingTable: bool = False
    recipe_links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self._seeingTable = True
            return

        if tag == 'a' and self._seeingTable:
            for (k, v) in attrs:
                if k == 'href' and is_valid_recipe_url(v):
                    self.recipe_links.append(v)
            return

    def handle_endtag(self, tag):
        if tag == 'table':
            self._seeingTable = False
            return

    def handle_data(self, data):
        pass


class HelloFreshRecipeParser(HTMLParser):
    # _seeingIngredient = False
    # _seeingP = False
    _seeingIngredient = False
    ingredients = []

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            for (k, v) in attrs:
                if k == "class" and v == "sc-5b343ba0-0 czDpDG":
                    self._seeingIngredient = True
        # for (k, v) in attrs:
        #     if k == "data-test-id" and v == "ingredient-item-shipped":
        #         self._seeingIngredient = True
        #         return
        #
        # if tag == "p":
        #     self._seeingP = True

    def handle_endtag(self, tag):
        # if tag == "p":
        #     self._seeingP = False
        self._seeingIngredient = False

    def handle_data(self, data):
        if self._seeingIngredient:
            self.ingredients.append(data)
        # if self._seeingIngredient and self._seeingP:
        #     self.ingredients.append(data)


recipeParser = HelloFreshRecipeParser()
r = requests.get('https://www.hellofresh.com/recipes/a-caesar-salad-to-rule-them-all-58f93531171c58372156c102',
                 headers={'User-Agent': 'test'})
if r.status_code == 200:
    recipeParser.feed(r.text)
    print(recipeParser.ingredients)
else:
    print(r.status_code)

# indexParser = HelloFreshIndexParser()
#
# r = requests.get('https://www.hellofresh.com/pages/sitemap/recipes-a', headers={'User-Agent': 'test'})
# if r.status_code == 200:
#     indexParser.feed(r.text)
#     print(indexParser.recipe_links)
# else:
#     print(r.status_code)
