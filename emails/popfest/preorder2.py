from emails.base import RasoiBoxEmail


class PreOrder2Email(RasoiBoxEmail):
    _subject: str = "PSA: Grab your Rasoi Box before they're gone"

    def __init__(self, to_email: str, from_email: str):
        super().__init__("popfest/preorder_2.html", {}, to_email, self._subject, from_email)
