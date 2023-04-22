from typing import Optional

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse


def _generate_token() -> str:
    return "token";


class AdminAuth(AuthenticationBackend):
    user: str
    password: str

    def __init__(self, user: str, password: str, secret_key: str):
        super().__init__(secret_key)
        self.user = user
        self.password = password

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form["username"], form["password"]

        if username == self.user and password == self.password:
            # Validate username/password credentials
            # And update session
            request.session.update({"token": _generate_token()})

            return True
        else:
            return False

    async def logout(self, request: Request) -> bool:
        # Usually you'd want to just clear the session
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> Optional[RedirectResponse]:
        token = request.session.get("token")

        if not token or token != _generate_token():
            return RedirectResponse(request.url_for("admin:login"), status_code=302)
