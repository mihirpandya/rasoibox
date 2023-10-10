from emails.base import RasoiBoxEmail


class InvitationEmail(RasoiBoxEmail):
    _subject: str = "Exciting News: Rasoi Box pre-orders open in your area!"

    def __init__(self, url_base: str, verification_code: str, promo_code: str, promo_amount: str, to_email: str,
                 from_email: str):
        template_args = {
            "promo_code": promo_code,
            "promo_amount": promo_amount,
            "create_account_link": self.create_account_link(url_base, verification_code)
        }
        super().__init__("invitation.html", template_args, to_email, self._subject, from_email)

    def create_account_link(self, url_base: str, verification_code: str) -> str:
        return "{}/signup?id={}".format(url_base, verification_code)
