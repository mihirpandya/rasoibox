from typing import List, Dict, Any

from emails.base import RasoiBoxEmail


class OrderDeliveredEmail(RasoiBoxEmail):
    _suffix: str = "Your Rasoi Box is delivered!"

    def __init__(self, url_base: str, first_name: str, line_items: List[Dict[str, Any]],
                 shipping_address: Dict[str, Any], order_id: str, to_email: str, from_email: str):
        subject = "Order {}: {}".format(order_id, self._suffix)
        template_args = {
            "order_link": self.order_link(url_base, order_id),
            "first_name": first_name,
            "line_items": line_items,
            "shipping_address": shipping_address,
            "order_id": order_id
        }

        super().__init__("order_delivered.html", template_args, to_email, subject, from_email)

    def order_link(self, url_base: str, order_id: str) -> str:
        return "{}/order?orderId={}".format(url_base, order_id)
