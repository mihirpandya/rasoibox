from emails.base import RasoiBoxEmail


class ResetPasswordEmail(RasoiBoxEmail):
    _subject: str = "Your Rasoi Box Account: Password Reset"

    def __init__(self, url_base: str, reset_code: str, to_email: str, from_email: str):
        template_args = {
            "reset_link": self.reset_link(url_base, reset_code)
        }
        super().__init__("reset_password_email.html", template_args, to_email, self._subject, from_email)

    def reset_link(self, url_base: str, reset_code: str) -> str:
        return "{}/reset?id={}".format(url_base, reset_code)