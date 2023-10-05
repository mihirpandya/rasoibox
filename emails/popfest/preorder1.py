from emails.base import RasoiBoxEmail


class PreOrder1Email(RasoiBoxEmail):
    _subject: str = "Rasoi Box Pop-Up at PopFest! Pre-Order Your Rasoi Box Today"

    def __init__(self, to_email: str, from_email: str):
        super().__init__("popfest/preorder_1.html", {}, to_email, self._subject, from_email)
