from emails.base import RasoiBoxEmail


class FollowUpEmail(RasoiBoxEmail):
    _subject: str = "Give your 2 cents, and Earn $5 towards your next Rasoi Box"

    def __init__(self, to_email: str, from_email: str):
        template_args = {
            "survey_link": self.survey_link()
        }
        super().__init__("followup.html", template_args, to_email, self._subject, from_email)

    def survey_link(self) -> str:
        return "https://forms.gle/4xBYVnDXYtKw73CH9"
