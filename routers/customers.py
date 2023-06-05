import logging
from datetime import datetime, timedelta
from typing import Annotated, Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status

from api.customers import NewCustomer
from config import Settings
from dependencies.database import get_db
from dependencies.oauth import oauth2_scheme
from emails.base import VerifySignUpEmail, send_email
from models.customers import Customer
from models.signups import VerifiedSignUp, UnverifiedSignUp
from routers.signup import jinjaEnv, smtp_server

logger = logging.getLogger("rasoibox")

settings: Settings = Settings()

SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

router = APIRouter(
    prefix="/api/users",
    tags=["users"]
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Token(BaseModel):
    access_token: str
    token_type: str


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db: Session, username: str) -> Customer:
    customer: Customer = db.query(Customer).filter(Customer.email == username).first()
    if customer is not None:
        return customer


def authenticate_user(username: str, password: str, db: Session):
    user = get_user(db, username)
    if user is None:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    if not user.verified:
        return False
    return user


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user(db, username=username)
    if user is None:
        raise credentials_exception
    return user


def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


@router.get("/items/")
async def read_items(token: Annotated[str, Depends(oauth2_scheme)]):
    return {"token": token}


@router.get("/users/me")
async def read_users_me(current_user: Annotated[Customer, Depends(get_current_user)]):
    return current_user


@router.post("/token", response_model=Token)
async def login_for_access_token(
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)
):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/create")
async def create_user_account(new_customer: NewCustomer, db: Session = Depends(get_db)):
    user = db.query(Customer).filter(Customer.email == new_customer.email).first()

    if user is not None and user.verified:
        logger.info("User already exists and verified: {}".format(new_customer.email))
        return
    elif user is None:
        verified_user = db.query(VerifiedSignUp).filter(VerifiedSignUp.email == new_customer.email).first()
        hashed_password = get_password_hash(new_customer.password)
        db.add(
            Customer(
                first_name=new_customer.first_name,
                last_name=new_customer.last_name,
                email=new_customer.email,
                hashed_password=hashed_password,
                join_date=new_customer.join_date,
                verified=(verified_user is not None)
            )
        )
        db.commit()

        if verified_user is None:
            # add to unverified table
            db.add(
                UnverifiedSignUp(
                    email=new_customer.email,
                    signup_date=new_customer.join_date,
                    signup_from="CREATE_ACCOUNT",
                    zipcode=new_customer.zipcode,
                    verification_code=new_customer.verification_code,
                )
            )
            db.commit()

            # send email with verification link
            url_base: str = settings.frontend_url_base[0:-1] if settings.frontend_url_base.endswith(
                "/") else settings.frontend_url_base
            verification_email: VerifySignUpEmail = VerifySignUpEmail(url_base,
                                                                      new_customer.verification_code,
                                                                      new_customer.email,
                                                                      settings.from_email)

            # send email best effort
            try:
                send_email(jinjaEnv, verification_email, smtp_server, settings.email, settings.email_app_password)
            except Exception as e:
                logger.error("Failed to send email.")
                logger.error(e)
