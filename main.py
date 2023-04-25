import datetime
import logging
import sqlite3
from imaplib import IMAP4_SSL
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqladmin import Admin
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse

from admin_auth.basic.base import AdminAuth
from api.signup.via_email import SignUpViaEmail
from config import Settings
from emails.base import VerifyUserEmail, send_email
from middleware.request_logger import RequestContextLogMiddleware
from models.base import Base
from models.user import UnverifiedUser, VerifiedUser
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
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

admin: Admin = Admin(app, engine, authentication_backend=AdminAuth(user=settings.admin_user,
                                                                   password=settings.admin_password, secret_key="test"))
admin.add_view(VerifiedUserAdmin)
admin.add_view(UnverifiedUserAdmin)

Base.metadata.create_all(engine)  # Create tables

imap_server: Optional[IMAP4_SSL] = None


def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


@app.on_event("startup")
async def startup_event():
    # connect to email server
    global imap_server
    imap_server = IMAP4_SSL("imap.gmail.com", 993)
    imap_server.login(settings.email, settings.email_app_password)
    GMAIL_DRAFTS = "[Gmail]/Drafts"
    imap_server.select(GMAIL_DRAFTS)
    logger.info("Email server is ready!")


@app.on_event("shutdown")
async def shutdown_event():
    global imap_server
    imap_server.close()
    logger.info("Shutting down gracefully!")
    return


@app.get("/healthz")
async def health():
    return


@app.post("/api/signup/email")
async def signup_via_email(sign_up_via_email: SignUpViaEmail, db: Session = Depends(get_db)):
    try:
        verified_user: Optional[VerifiedUser] = db.query(VerifiedUser).filter(
            VerifiedUser.first_name == sign_up_via_email.first_name
            and VerifiedUser.last_name == sign_up_via_email.last_name
            and VerifiedUser.email == sign_up_via_email.email
            and VerifiedUser.zipcode == sign_up_via_email.zipcode).first()

        if verified_user is not None:
            logger.info("User already verified.", sign_up_via_email)

            return JSONResponse(content=jsonable_encoder({"status": 0, "message": "User already verified."}))

        unverified_user: Optional[UnverifiedUser] = db.query(UnverifiedUser).filter(
            UnverifiedUser.first_name == sign_up_via_email.first_name
            and UnverifiedUser.last_name == sign_up_via_email.last_name
            and UnverifiedUser.email == sign_up_via_email.email
            and UnverifiedUser.zipcode == sign_up_via_email.zipcode).first()

        message: str
        status_code: int
        verification_code: str
        if unverified_user is not None:
            logger.info("User already signed up but not verified. Resending verification email.", sign_up_via_email)
            verification_code = unverified_user.verification_code
            status_code = 1
            message = "User already signed up but not verified. Verification email re-sent"
        else:
            status_code = 2
            message = "Verification email sent"
            # generate random UUID as verification code
            verification_code: str = str(uuid4())

            # insert entry in db
            db.add(
                UnverifiedUser(
                    first_name=sign_up_via_email.first_name,
                    last_name=sign_up_via_email.last_name,
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
        verification_email: VerifyUserEmail = VerifyUserEmail(templates.get_template("verify_email.html"),
                                                              url_base,
                                                              sign_up_via_email.first_name,
                                                              verification_code,
                                                              sign_up_via_email.email,
                                                              settings.from_email)

        # send email best effort
        try:
            send_email(verification_email, imap_server)
        except Exception as e:
            logger.error("Failed to send email.", e)

        return JSONResponse(content={"status": status_code, "message": message})
    except sqlite3.OperationalError as e:
        logger.error("Failed to save data.", sign_up_via_email, e)
        raise HTTPException(status_code=500, detail="Failed to save data.")


@app.get("/api/verify/email")
async def verify_email(id: str, db: Session = Depends(get_db)) -> JSONResponse:
    unverified_user: Optional[UnverifiedUser] = db.query(UnverifiedUser).filter(
        UnverifiedUser.verification_code == id).first()

    if unverified_user is not None:
        join_date = datetime.datetime.now()
        db.add(
            VerifiedUser(
                first_name=unverified_user.first_name,
                last_name=unverified_user.last_name,
                email=unverified_user.email,
                signup_date=unverified_user.signup_date,
                signup_from=unverified_user.signup_from,
                zipcode=unverified_user.zipcode,
                join_date=join_date,
                verification_code=unverified_user.verification_code
            )
        )

        db.delete(unverified_user)
        db.commit()

    verified_user: Optional[VerifiedUser] = db.query(VerifiedUser).filter(VerifiedUser.verification_code == id).first()
    if verified_user is not None:
        response = {
            "first_name": verified_user.first_name,
            "last_name": verified_user.last_name
        }
        return JSONResponse(content=jsonable_encoder(response))
    else:
        raise HTTPException(status_code=404, detail="Invalid verification code.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9000,
        log_config=logging.basicConfig(level=logging.INFO)
    )
