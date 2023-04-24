import datetime
import logging
import sqlite3
from imaplib import IMAP4_SSL
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqladmin import Admin
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from starlette.middleware.sessions import SessionMiddleware

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
    "sqlite:///" + settings.db_path,
    connect_args={"check_same_thread": False},
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
                verification_code=verification_code
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

        send_email(verification_email, imap_server)

        return
    except sqlite3.OperationalError as e:
        logger.error("Failed to save data.", sign_up_via_email, e)
        raise HTTPException(status_code=500, detail="Failed to save data.")


@app.get("/api/verify/email")
async def verify_email(id: str, db: Session = Depends(get_db)):
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
                join_date=join_date
            )
        )

        db.delete(unverified_user)
        db.commit()
        return
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
