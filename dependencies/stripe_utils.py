import logging
from typing import List

import stripe

from config import Settings

logger = logging.getLogger(__name__)

settings = Settings()

stripe.api_key = settings.stripe_secret_key


def to_product_name(name: str, serving_size: int) -> str:
    return "{} servings of {}".format(str(serving_size), name)


def to_cents(price: float) -> int:
    return int(round(price * 100))


def create_stripe_product_idempotent(recipe_name: str, description: str, image_url: str, serving_size: int,
                                     price: float):
    product = get_stripe_product(recipe_name, serving_size)
    if product is None:
        return create_stripe_product(recipe_name, description, image_url, serving_size, price)
    else:
        change = description != product["description"] or [image_url] != product["images"]
        if change:
            return update_stripe_product(product["id"], description, image_url)
        return product


def update_stripe_product(product_id: str, description: str, image_url: str):
    return stripe.Product.modify(
        product_id,
        description=description,
        images=[image_url]
    )


def create_stripe_product(recipe_name: str, description: str, image_url: str, serving_size: int, price: float):
    price_cents: int = to_cents(price)
    price_data = {
        "currency": "usd",
        "unit_amount": price_cents
    }
    product_name: str = to_product_name(recipe_name, serving_size)
    return stripe.Product.create(
        name=product_name,
        active=True,
        description=description,
        metadata={
            "serving_size": serving_size,
        },
        shippable=True,
        images=[image_url],
        default_price_data=price_data,
        unit_label="item"
    )


def get_stripe_product_from_id(product_id: str):
    return stripe.Product.retrieve(product_id)


def get_stripe_product(recipe_name: str, serving_size: int):
    product_name: str = to_product_name(recipe_name, serving_size)
    query = "name:\"{}\"".format(product_name)
    logger.debug("Sending search query: {}".format(query))
    search_results = stripe.Product.search(query=query)
    if "data" in search_results:
        if len(search_results["data"]) > 0:
            return search_results["data"][0]
    else:
        logger.warning("Strip API did not return a data entry.")
    return None


def create_checkout_session(price_ids: List[str], success_url: str, cancel_url: str, user_facing_order_id: str,
                            email: str, discounts: List[str] = None):
    line_items = [{"price": price_id, "quantity": 1} for price_id in price_ids]
    promo_codes = [find_promo_code_id(x)["id"] for x in discounts] if discounts is not None else []
    discount_arr = [{"promotion_code": x} for x in promo_codes if x is not None]
    return stripe.checkout.Session.create(
        line_items=line_items,
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        discounts=discount_arr,
        automatic_tax={
            'enabled': True
        },
        client_reference_id=user_facing_order_id,
        customer_email=email,
        # shipping_address_collection={
        #     'allowed_countries': ['US']
        # }
    )


def find_promo_code_id(promo_code: str):
    promo_codes = stripe.PromotionCode.list(code=promo_code)
    if "data" in promo_codes and len(promo_codes["data"]) == 1:
        return promo_codes["data"][0]
    else:
        return None


def create_promo_code_from_coupon(stripe_coupon_id: str, customer_facing_code: str):
    return stripe.PromotionCode.create(
        coupon=stripe_coupon_id,
        code=customer_facing_code,
        max_redemptions=1
    )
