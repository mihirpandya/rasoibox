from emails.base import RasoiBoxEmail


class ReferralAuthEmail(RasoiBoxEmail):
    _suffix: str = " is inviting you to try Rasoi Box!"

    def __init__(self, url_base: str, first_name: str, last_name: str, verification_code: str, promo_code: str,
                 promo_amount: str, to_email: str, from_email: str):
        subject = first_name + self._suffix
        template_args = {
            "promo_code": promo_code,
            "promo_amount": promo_amount,
            "full_name": first_name + " " + last_name,
            "create_account_link": self.create_account_link(url_base, verification_code)
        }
        super().__init__("auth_referral.html", template_args, to_email, subject, from_email)

    def create_account_link(self, url_base, verification_code):
        return "{}/createaccount?id={}".format(url_base, verification_code)