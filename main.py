import datetime
import logging
import sqlite3
from smtplib import SMTP
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqladmin import Admin
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse

from admin_auth.basic.base import AdminAuth
from api.menu import MenuEvent
from api.recipes import CandidateRecipe, StarRecipe
from api.signup import SignUpViaEmail
from api.welcome import WelcomeEvent
from config import Settings
from emails.base import VerifySignUpEmail, send_email
from middleware.request_logger import RequestContextLogMiddleware
from models.base import Base
from models.event import Event
from models.recipes import RecipeContributor, Recipe
from models.signups import UnverifiedSignUp, VerifiedSignUp
from views.event import EventAdmin
from views.user import VerifiedUserAdmin, UnverifiedUserAdmin

logger = logging.getLogger("rasoibox")

settings: Settings = Settings()
engine = create_engine(
    settings.db_path,
)
jinjaEnv = Environment(loader=FileSystemLoader("templates"), autoescape=select_autoescape())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="test")
app.add_middleware(RequestContextLogMiddleware, request_logger=logger)

admin: Admin = Admin(app, engine, authentication_backend=AdminAuth(user=settings.admin_user,
                                                                   password=settings.admin_password, secret_key="test"))
admin.add_view(VerifiedUserAdmin)
admin.add_view(UnverifiedUserAdmin)
admin.add_view(EventAdmin)

Base.metadata.create_all(engine)  # Create tables

smtp_server: SMTP = SMTP('smtp.gmail.com', 587)


def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def emit_event(db: Session, event_type: str, event_timestamp: datetime, code: str, referrer_opt: Optional[str]):
    try:
        referrer = referrer_opt if referrer_opt is not None else "NONE"
        event = Event(event_type=event_type, event_timestamp=event_timestamp, code=code, referrer=referrer)
        db.add(event)
        db.commit()
    except Exception as e:
        logger.error("Failed to save event.")
        logger.error(e)
        return


@app.on_event("startup")
async def startup_event():
    logger.info("Server started successfully!")


@app.on_event("shutdown")
async def shutdown_event():
    global smtp_server
    smtp_server.close()
    logger.info("Shutting down gracefully!")
    return


@app.get("/healthz")
async def health():
    return


@app.post("/api/welcome")
async def welcome(welcome_event: WelcomeEvent, db: Session = Depends(get_db)):
    emit_event(db, "WELCOME", welcome_event.welcome_date, welcome_event.verification_code, welcome_event.referrer)
    return


@app.post("/api/menu")
async def menu(menu_event: MenuEvent, db: Session = Depends(get_db)):
    emit_event(db, "MENU", menu_event.menu_date, menu_event.verification_code, menu_event.referrer)
    return


@app.post("/api/signup/email")
async def signup_via_email(sign_up_via_email: SignUpViaEmail, db: Session = Depends(get_db)):
    try:
        verified_sign_up: Optional[VerifiedSignUp] = db.query(VerifiedSignUp).filter(
            VerifiedSignUp.email == sign_up_via_email.email
            and VerifiedSignUp.zipcode == sign_up_via_email.zipcode).first()

        if verified_sign_up is not None:
            logger.info("User already verified.")

            return JSONResponse(content=jsonable_encoder({
                "status": 0,
                "message": "User already verified.",
                "verification_code": verified_sign_up.verification_code
            }))

        unverified_sign_up: Optional[UnverifiedSignUp] = db.query(UnverifiedSignUp).filter(
            UnverifiedSignUp.email == sign_up_via_email.email
            and UnverifiedSignUp.zipcode == sign_up_via_email.zipcode).first()

        message: str
        status_code: int
        verification_code: str
        if unverified_sign_up is not None:
            logger.info("User already signed up but not verified. Resending verification email.")
            verification_code = unverified_sign_up.verification_code
            status_code = 1
            message = "User already signed up but not verified. Verification email re-sent"
        else:
            verification_code = sign_up_via_email.verification_code
            status_code = 2
            message = "Verification email sent"
            emit_event(db, "NEW_SIGN_UP", sign_up_via_email.signup_date, sign_up_via_email.verification_code,
                       sign_up_via_email.referrer)

            # insert entry in db
            db.add(
                UnverifiedSignUp(
                    email=sign_up_via_email.email,
                    signup_date=sign_up_via_email.signup_date,
                    signup_from="EMAIL",
                    zipcode=sign_up_via_email.zipcode,
                    verification_code=verification_code,
                )
            )

            db.commit()

        # send email with verification link
        url_base: str = settings.frontend_url_base[0:-1] if settings.frontend_url_base.endswith(
            "/") else settings.frontend_url_base
        verification_email: VerifySignUpEmail = VerifySignUpEmail(url_base,
                                                                  verification_code,
                                                                  sign_up_via_email.email,
                                                                  settings.from_email)

        # send email best effort
        try:
            send_email(jinjaEnv, verification_email, smtp_server, settings.email, settings.email_app_password)
        except Exception as e:
            logger.error("Failed to send email.")
            logger.error(e)

        return JSONResponse(content={"status": status_code, "message": message, "verification_code": verification_code})
    except sqlite3.OperationalError as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Failed to save data.")


@app.get("/api/verify/email")
async def verify_email(id: str, db: Session = Depends(get_db)) -> JSONResponse:
    unverified_sign_up: Optional[UnverifiedSignUp] = db.query(UnverifiedSignUp).filter(
        UnverifiedSignUp.verification_code == id).first()

    if unverified_sign_up is not None:
        verify_date = datetime.datetime.now()
        db.add(
            VerifiedSignUp(
                email=unverified_sign_up.email,
                signup_date=unverified_sign_up.signup_date,
                signup_from=unverified_sign_up.signup_from,
                zipcode=unverified_sign_up.zipcode,
                verify_date=verify_date,
                verification_code=unverified_sign_up.verification_code
            )
        )

        db.delete(unverified_sign_up)
        db.commit()
        emit_event(db, "VERIFY", verify_date, unverified_sign_up.verification_code, None)

    verified_sign_up: Optional[VerifiedSignUp] = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.verification_code == id).first()
    if verified_sign_up is not None:
        return JSONResponse(content=jsonable_encoder({}))
    else:
        raise HTTPException(status_code=404, detail="Invalid verification code.")


@app.get("/api/verified")
async def is_verified_sign_up(id: str, db: Session = Depends(get_db)) -> JSONResponse:
    verified_sign_up: Optional[VerifiedSignUp] = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.verification_code == id).first()

    verified: bool = True if verified_sign_up is not None else False

    return JSONResponse(content=jsonable_encoder({"verified": verified}))


@app.post("/api/recipe/add")
async def add_recipes(recipes: List[CandidateRecipe], db: Session = Depends(get_db)):
    recipes_to_add: List[Recipe] = []
    created_date = datetime.datetime.now()
    for recipe in recipes:
        contributor_name = recipe.recipe_contributor_name
        contributor = db.query(RecipeContributor).filter(RecipeContributor.name == contributor_name).first()
        if contributor is None:
            raise HTTPException(status_code=404, detail="Unrecognized contributor {}.".format(contributor_name))

        recipes_to_add.append(
            Recipe(
                name=recipe.name,
                created_date=created_date,
                description=recipe.description,
                image_url=recipe.image_url,
                recipe_contributor_id=contributor.id
            )
        )

    db.add_all(recipes_to_add)
    db.commit()
    return


@app.post("/api/recipe/star")
async def star_recipe(recipe_to_star: StarRecipe, db: Session = Depends(get_db)):
    star_date = datetime.datetime.now()
    recipe: Recipe = db.query(Recipe).filter(Recipe.name == recipe_to_star.recipe_name).first()
    starred_by: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.verification_code == recipe_to_star.verification_code).first()

    if recipe is None:
        raise HTTPException(status_code=404, detail="Unrecognized recipe {}.".format(recipe_to_star.recipe_name))

    if starred_by is None:
        raise HTTPException(status_code=404, detail="Unverified user.")

    db.add(
        StarRecipe(
            recipe_id=recipe.id,
            verified_sign_up_id=starred_by.id,
            starred_date=star_date
        )
    )

    db.commit()
    return


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9000,
        log_config=logging.basicConfig(level=logging.INFO)
    )
