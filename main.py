import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles
from sqladmin import Admin
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.wsgi import WSGIMiddleware

from admin_auth.basic.base import AdminAuth
from config import Settings
from dashapp.dashapp import create_dash_app
from dependencies.database import get_engine, get_db
from middleware.request_logger import RequestContextLogMiddleware
from models.base import Base
from routers import recipe, signup, customers, order, price, orderV2, popfest
from views.customers import CustomerAdmin
from views.event import EventAdmin, RecipeEventAdmin
from views.invitations import InvitationAdmin
from views.orders import OrderAdmin, CartAdmin, PromoCodeAdmin
from views.recipes import RecipeContributorAdmin, RecipeAdmin, StarredRecipeAdmin, RecipeScheduleAdmin, \
    InYourKitchenAdmin, IngredientsAdmin, RecipeIngredientsAdmin, RecipeInYourKitchenAdmin, RecipeStepAdmin, \
    RecipePriceAdmin
from views.reset_passwords import ResetPasswordsAdmin
from views.user import VerifiedUserAdmin, UnverifiedUserAdmin, DeliverableZipcodeAdmin

logger = logging.getLogger("rasoibox")

settings: Settings = Settings()

origins = [
    "http://localhost",
    "http://localhost:8081",
    "http://192.168.68.60",
    "http://192.168.68.60:8081",
    "https://rasoibox-expo.vercel.app",
    "https://www.rasoibox.com",
]

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="test")
app.add_middleware(RequestContextLogMiddleware, request_logger=logger)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = get_engine()

# Admin views
admin: Admin = Admin(app, engine, authentication_backend=AdminAuth(user=settings.admin_user,
                                                                   password=settings.admin_password, secret_key="test"))
admin.add_view(VerifiedUserAdmin)
admin.add_view(UnverifiedUserAdmin)
admin.add_view(DeliverableZipcodeAdmin)
admin.add_view(EventAdmin)
admin.add_view(RecipeContributorAdmin)
admin.add_view(RecipeAdmin)
admin.add_view(StarredRecipeAdmin)
admin.add_view(RecipeScheduleAdmin)
admin.add_view(InYourKitchenAdmin)
admin.add_view(IngredientsAdmin)
admin.add_view(RecipeIngredientsAdmin)
admin.add_view(RecipeInYourKitchenAdmin)
admin.add_view(RecipeStepAdmin)
admin.add_view(RecipePriceAdmin)
admin.add_view(RecipeEventAdmin)
admin.add_view(CustomerAdmin)
admin.add_view(ResetPasswordsAdmin)
admin.add_view(OrderAdmin)
admin.add_view(CartAdmin)
admin.add_view(PromoCodeAdmin)
admin.add_view(InvitationAdmin)

# Create tables
Base.metadata.create_all(engine)

# Dashboard
dash_app = create_dash_app(next(get_db()), requests_pathname_prefix="/dash/")
app.mount("/dash", WSGIMiddleware(dash_app.server))

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# API Routers
app.include_router(recipe.router)
app.include_router(signup.router)
app.include_router(customers.router)
app.include_router(order.router)
app.include_router(price.router)
app.include_router(orderV2.router)
app.include_router(popfest.router)


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
