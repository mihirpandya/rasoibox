from emails.base import RasoiBoxEmail


class InvitationCompleteEmail(RasoiBoxEmail):
    _suffix: str = " has unlocked your Rasoi Box referral bonus!"

    def __init__(self, url_base: str, verification_code: str, referred_first_name: str, promo_code: str,
                 promo_amount: str, to_email: str, from_email: str):
        subject = referred_first_name + self._suffix
        template_args = {
            "promo_code": promo_code,
            "promo_amount": promo_amount,
            "referred_first_name": referred_first_name,
            "create_account_link": self.create_account_link(url_base, verification_code)
        }
        super().__init__("invitation_complete.html", template_args, to_email, subject, from_email)

    def create_account_link(self, url_base: str, verification_code: str) -> str:
        return "{}/signup?id={}".format(url_base, verification_code)
