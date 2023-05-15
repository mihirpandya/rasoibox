import datetime
import logging
import sqlite3
from smtplib import SMTP
from typing import Optional, List, Dict

from fastapi import FastAPI, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqladmin import Admin
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse

from admin_auth.basic.base import AdminAuth
from api.event import SiteEvent
from api.recipes import CandidateRecipe, StarRecipe
from api.signup import SignUpViaEmail
from config import Settings
from emails.base import VerifySignUpEmail, send_email
from middleware.request_logger import RequestContextLogMiddleware
from models.base import Base
from models.event import Event
from models.recipes import RecipeContributor, Recipe, StarredRecipe, RecipeSchedule
from models.signups import UnverifiedSignUp, VerifiedSignUp
from views.event import EventAdmin
from views.recipes import RecipeContributorAdmin, RecipeAdmin, StarredRecipeAdmin, RecipeScheduleAdmin
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
admin.add_view(RecipeContributorAdmin)
admin.add_view(RecipeAdmin)
admin.add_view(StarredRecipeAdmin)
admin.add_view(RecipeScheduleAdmin)

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


@app.post("/api/event")
async def event(site_event: SiteEvent, db: Session = Depends(get_db)):
    emit_event(db, site_event.event_type, site_event.event_date, site_event.verification_code, site_event.referrer)
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
    recipes_to_add: Dict[str, Recipe] = {}
    created_date = datetime.datetime.now()
    for recipe in recipes:
        contributor_name = recipe.contributor_name
        contributor = db.query(RecipeContributor).filter(RecipeContributor.name == contributor_name).first()
        if contributor is None:
            raise HTTPException(status_code=401, detail="Unrecognized contributor: {}.".format(contributor_name))

        existing_recipe = db.query(Recipe).filter(Recipe.name == recipe.recipe_name).first()
        if existing_recipe is not None:
            raise HTTPException(status_code=400, detail="Recipe with the same name already exists.")

        if recipe.recipe_name in recipes_to_add.keys():
            raise HTTPException(status_code=400, detail="Recipe names must be unique: {}.".format(recipe.recipe_name))

        recipes_to_add[recipe.recipe_name] = Recipe(
            name=recipe.recipe_name,
            created_date=created_date,
            description=recipe.description,
            image_url=recipe.image_url,
            recipe_contributor_id=contributor.id
        )

    db.add_all(list(recipes_to_add.values()))
    db.commit()
    return


@app.post("/api/recipe/star")
async def toggle_star_recipe(recipe_to_star: StarRecipe, db: Session = Depends(get_db)):
    star_date = datetime.datetime.now()
    recipe: Recipe = db.query(Recipe).filter(Recipe.name == recipe_to_star.recipe_name).first()
    starred_by: VerifiedSignUp = db.query(VerifiedSignUp).filter(
        VerifiedSignUp.verification_code == recipe_to_star.verification_code).first()

    if recipe is None:
        raise HTTPException(status_code=404, detail="Unrecognized recipe: {}.".format(recipe_to_star.recipe_name))

    if starred_by is None:
        raise HTTPException(status_code=401, detail="Unverified user.")

    existing_star: StarredRecipe = db.query(StarredRecipe).filter(
        StarredRecipe.recipe_id == recipe.id and StarredRecipe.verified_sign_up_id == starred_by.id).first()

    if existing_star is None:
        db.add(
            StarredRecipe(
                recipe_id=recipe.id,
                verified_sign_up_id=starred_by.id,
                starred_date=star_date
            )
        )
    else:
        db.delete(existing_star)

    db.commit()
    return


@app.get("/api/recipe/stars")
async def get_stars_for_user(id: str, db: Session = Depends(get_db)) -> JSONResponse:
    verified_user = db.query(VerifiedSignUp).filter(VerifiedSignUp.verification_code == id).first()
    if verified_user is None:
        raise HTTPException(status_code=401, detail="Unrecognized user.")

    starred_recipes: List[StarredRecipe] = db.query(StarredRecipe).filter(StarredRecipe.verified_sign_up_id == id).all()
    result = []
    for starred_recipe in starred_recipes:
        recipe: Recipe = db.query(Recipe).filter(Recipe.id == starred_recipe.recipe_id).first()
        result.append(recipe.name)
    return JSONResponse(content=jsonable_encoder(result))


@app.get("/api/recipe/schedule")
async def get_recipe_schedule(id: str, db: Session = Depends(get_db)) -> JSONResponse:
    verified_user = db.query(VerifiedSignUp).filter(VerifiedSignUp.verification_code == id).first()
    if verified_user is None:
        raise HTTPException(status_code=401, detail="Unrecognized user.")
    result = {}
    recipe_schedule: List[RecipeSchedule] = db.query(RecipeSchedule).order_by(
        RecipeSchedule.schedule_start_date.asc()).all()
    for item in recipe_schedule:
        recipe: Recipe = db.query(Recipe).filter(Recipe.id == item.recipe_id).first()
        if recipe is None:
            logger.error("Schedule has invalid recipe_id: {} {}".format(item.id, item.recipe_id))
        else:
            if item.schedule_start_date not in result:
                result[item.schedule_start_date] = []
            result[item.schedule_start_date].append({
                "id": recipe.id,
                "name": recipe.name,
                "description": recipe.description,
                "image_url": recipe.image_url
            })

    return JSONResponse(content=jsonable_encoder(result))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9000,
        log_config=logging.basicConfig(level=logging.INFO)
    )
