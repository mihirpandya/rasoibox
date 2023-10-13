from emails.base import RasoiBoxEmail


class CreatePasswordEmail(RasoiBoxEmail):
    _subject: str = "Rasoi Box: Before cooking your first meal"

    def __init__(self, url_base: str, first_name: str, create_id: int, payment_intent: str, to_email: str,
                 from_email: str):
        template_args = {
            "first_name": first_name,
            "create_account_link": self.create_account_link(url_base, create_id, payment_intent)
        }
        super().__init__("create_password.html", template_args, to_email, self._subject, from_email)

    def create_account_link(self, url_base: str, create_id: int, payment_intent: str) -> str:
        return "{}/createpassword?create_id={}&payment_intent={}".format(url_base, str(create_id), payment_intent)
