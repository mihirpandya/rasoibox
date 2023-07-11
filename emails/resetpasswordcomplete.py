from emails.base import RasoiBoxEmail


class ResetPasswordCompleteEmail(RasoiBoxEmail):
    _subject: str = "Your Rasoi Box password has been reset"

    def __init__(self, first_name: str, to_email: str, from_email: str):
        template_args = {
            "first_name": first_name
        }
        super().__init__("reset_password_complete_email.html", template_args, to_email, self._subject, from_email)