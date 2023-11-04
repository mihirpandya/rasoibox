from typing import List, Dict, Any

from emails.base import RasoiBoxEmail


class OrderComingTodayEmail(RasoiBoxEmail):
    _suffix: str = "Your Rasoi Box is coming today!"

    def __init__(self, url_base: str, first_name: str, estimated_delivery: str, line_items: List[Dict[str, Any]],
                 shipping_address: Dict[str, Any], order_id: str, to_email: str, from_email: str):
        subject = "Order {}: {}".format(order_id, self._suffix)
        template_args = {
            "order_link": self.order_link(url_base, order_id),
            "first_name": first_name,
            "line_items": line_items,
            "shipping_address": self.shipping_address(shipping_address),
            "order_id": order_id,
            "estimated_delivery": estimated_delivery
        }

        super().__init__("order_coming_today.html", template_args, to_email, subject, from_email)

    def order_link(self, url_base: str, order_id: str) -> str:
        return "{}/order/{}".format(url_base, order_id)

    def shipping_address(self, address: Dict[str, Any]) -> str:
        if 'apartment_number' in address.keys() and address['apartment_number'] is not None and len(
                address['apartment_number']) > 0:
            return "{}, {}, {}, {} {}".format(address['street_name'], address['apartment_number'], address['city'],
                                              address['state'], address['zipcode'])
        else:
            return "{}, {}, {} {}".format(address['street_name'], address['city'], address['state'], address['zipcode'])
