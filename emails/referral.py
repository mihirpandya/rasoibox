from emails.base import RasoiBoxEmail


class ReferralEmail(RasoiBoxEmail):
    _subject: str = "Your friend is inviting you to try Rasoi Box!"

    def __init__(self, url_base: str, referrer_email: str, verification_code: str, promo_code: str,
                 promo_amount: str, to_email: str, from_email: str):
        template_args = {
            "promo_code": promo_code,
            "promo_amount": promo_amount,
            "referrer_email": referrer_email,
            "create_account_link": self.create_account_link(url_base, verification_code)
        }
        super().__init__("referral.html", template_args, to_email, self._subject, from_email)

    def create_account_link(self, url_base, verification_code):
        return "{}/createaccount?id={}".format(url_base, verification_code)