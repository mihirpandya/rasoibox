from datetime import datetime, timedelta

from fastapi import Depends, HTTPException
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from starlette import status

from config import Settings
from dependencies.database import get_db
from dependencies.oauth import oauth2_scheme
from models.customers import Customer

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

settings: Settings = Settings()

SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def create_access_token(data: dict):
    to_encode = data.copy()
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_customer(db: Session, username: str) -> Customer:
    customer: Customer = db.query(Customer).filter(Customer.email == username).first()
    if customer is not None:
        return customer


def authenticate_customer(username: str, password: str, db: Session):
    user = get_customer(db, username)
    if user is None:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    if not user.verified:
        return False
    return user


async def get_current_customer(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Customer:
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
    customer = get_customer(db, username=username)
    if customer is None:
        raise credentials_exception
    return customer
