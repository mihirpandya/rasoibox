from typing import List, Dict, Any

from emails.base import RasoiBoxEmail


class OrderPickedUpEmail(RasoiBoxEmail):
    _suffix: str = "Your Rasoi Box is picked up!"

    def __init__(self, url_base: str, first_name: str, create_id: int, payment_intent: str, create_account: bool,
                 line_items: List[Dict[str, Any]], shipping_address: Dict[str, Any], order_id: str, to_email: str,
                 from_email: str):
        subject = "Order {}: {}".format(order_id, self._suffix)
        template_args = {
            "create_account": create_account,
            "create_account_link": self.create_account_link(url_base, create_id, payment_intent),
            "order_link": self.order_link(url_base, order_id),
            "first_name": first_name,
            "line_items": line_items,
            "shipping_address": shipping_address,
            "order_id": order_id
        }

        super().__init__("order_pickedup.html", template_args, to_email, subject, from_email)

    def order_link(self, url_base: str, order_id: str) -> str:
        return "{}/order/{}".format(url_base, order_id)

    def create_account_link(self, url_base: str, create_id: int, payment_intent: str) -> str:
        return "{}/createpassword?create_id={}&payment_intent={}".format(url_base, str(create_id), payment_intent)
