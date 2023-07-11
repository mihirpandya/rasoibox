from emails.base import RasoiBoxEmail


class InvitationCompleteEmail(RasoiBoxEmail):
    _suffix: str = " has unlocked your Rasoi Box referral bonus!"

    def __init__(self, referred_first_name: str, promo_code: str, promo_amount: str, to_email: str, from_email: str):
        subject = referred_first_name + self._suffix
        template_args = {
            "promo_code": promo_code,
            "promo_amount": promo_amount,
            "referred_first_name": referred_first_name
        }
        super().__init__("invitation_complete.html", template_args, to_email, subject, from_email)