from emails.base import RasoiBoxEmail


class VerifySignUpEmail(RasoiBoxEmail):
    _subject: str = "Hello from Rasoi Box! Please verify your email."

    def __init__(self, url_base: str, verification_code: str, to_email: str,
                 from_email: str):
        template_args = {
            "verification_link": self.verification_link(url_base, verification_code)
        }
        super().__init__("verify_email.html", template_args, to_email, self._subject, from_email)

    def verification_link(self, url_base: str, verification_code: str) -> str:
        return "{}/menu?id={}".format(url_base, verification_code)
