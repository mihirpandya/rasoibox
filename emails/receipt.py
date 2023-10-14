from typing import List, Dict, Any

from emails.base import RasoiBoxEmail


class ReceiptEmail(RasoiBoxEmail):
    _subject: str = "Rasoi Box Order Confirmation"

    def __init__(self, url_base: str, first_name: str, line_items: List[Dict[str, Any]], promo_code: Dict[str, Any],
                 total: float, sub_total: float, shipping_fee: str, shipping_address: Dict[str, Any], order_id: str,
                 estimated_delivery: str, to_email: str, from_email: str):
        subject = self._subject + ": " + order_id
        template_args = {
            "order_link": self.order_link(url_base, order_id),
            "first_name": first_name,
            "subtotal": "{:.2f}".format(sub_total),
            "total": "{:.2f}".format(total),
            "line_items": line_items,
            "shipping_fee": shipping_fee,
            "shipping_address": self.shipping_address(shipping_address),
            "order_id": order_id,
            "estimated_delivery": estimated_delivery
        }

        if len(promo_code) > 0:
            discount_str = ""
            if promo_code["amount_off"] is not None and promo_code["amount_off"] > 0:
                discount_str = "-$" + "{:.2f}".format(promo_code["amount_off"])
            elif promo_code["percent_off"] is not None and promo_code["percent_off"] > 0:
                discount_str = "-" + str(int(promo_code["percent_off"])) + "%"
            template_args["promo_code"] = {
                "name": promo_code["name"],
                "discount_str": discount_str
            }

        super().__init__("receipt.html", template_args, to_email, subject, from_email)

    def order_link(self, url_base: str, order_id: str) -> str:
        return "{}/order/{}".format(url_base, order_id)

    def shipping_address(self, address: Dict[str, Any]) -> str:
        if 'apartment_number' in address.keys() and address['apartment_number'] is not None and len(
                address['apartment_number']) > 0:
            return "{}, {}, {}, {} {}".format(address['street_name'], address['apartment_number'], address['city'],
                                              address['state'], address['zipcode'])
        else:
            return "{}, {}, {} {}".format(address['street_name'], address['city'], address['state'], address['zipcode'])
