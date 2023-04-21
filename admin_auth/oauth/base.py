from typing import Optional

from authlib.integrations.base_client import BaseOAuth
from sqladmin.authentication import AuthenticationBackend
from starlette.datastructures import URL
from starlette.requests import Request
from starlette.responses import RedirectResponse


class AdminOAuth(AuthenticationBackend):
    oauth: BaseOAuth

    def __init__(self, secret_key: str, oauth: BaseOAuth):
        super().__init__(secret_key)
        self.oauth = oauth

    async def login(self, request: Request) -> bool:
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> Optional[RedirectResponse]:
        user = request.session.get("user")
        if not user:
            redirect_uri: URL = request.url_for('login_google')
            print("LOGIN GOOGLE")
            print(redirect_uri)
            return await self.oauth.authorize_redirect(request, str(redirect_uri))
