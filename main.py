import logging

from fastapi import FastAPI
from sqladmin import Admin
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.wsgi import WSGIMiddleware

from admin_auth.basic.base import AdminAuth
from config import Settings
from dashapp.dashapp import create_dash_app
from middleware.request_logger import RequestContextLogMiddleware
from models.base import Base
from routers import recipe, signup
from views.event import EventAdmin
from views.recipes import RecipeContributorAdmin, RecipeAdmin, StarredRecipeAdmin, RecipeScheduleAdmin
from views.user import VerifiedUserAdmin, UnverifiedUserAdmin

logger = logging.getLogger("rasoibox")

settings: Settings = Settings()
engine = create_engine(
    settings.db_path,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="test")
app.add_middleware(RequestContextLogMiddleware, request_logger=logger)

admin: Admin = Admin(app, engine, authentication_backend=AdminAuth(user=settings.admin_user,
                                                                   password=settings.admin_password, secret_key="test"))
admin.add_view(VerifiedUserAdmin)
admin.add_view(UnverifiedUserAdmin)
admin.add_view(EventAdmin)
admin.add_view(RecipeContributorAdmin)
admin.add_view(RecipeAdmin)
admin.add_view(StarredRecipeAdmin)
admin.add_view(RecipeScheduleAdmin)

Base.metadata.create_all(engine)  # Create tables

dash_app = create_dash_app(SessionLocal(), requests_pathname_prefix="/dash/")
app.mount("/dash", WSGIMiddleware(dash_app.server))

app.include_router(recipe.router)
app.include_router(signup.router)


@app.on_event("startup")
async def startup_event():
    logger.info("Server started successfully!")


@app.on_event("shutdown")
async def shutdown_event():
    from routers.signup import smtp_server
    smtp_server.close()
    logger.info("Shutting down gracefully!")
    return


@app.get("/healthz")
async def health():
    return


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9000,
        log_config=logging.basicConfig(level=logging.INFO)
    )
