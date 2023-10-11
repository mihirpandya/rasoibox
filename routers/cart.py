import logging
from typing import List, Dict, Optional

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from config import Settings
from dependencies.database import get_db
from models.orders import Cart
from models.signups import VerifiedSignUp, UnverifiedSignUp

logger = logging.getLogger("rasoibox")

router = APIRouter(
    prefix="/api/cart",
    tags=["cart"]
)

settings: Settings = Settings()


@router.get('/active_carts')
async def get_active_carts(db: Session = Depends(get_db)):
    all_cart_items: List[Cart] = db.query(Cart).all()
    result: Dict[str, List[int]] = {}
    emailable_code: Dict[str, str] = {}
    for cart_item in all_cart_items:
        email: Optional[str] = None

        if cart_item.verification_code in emailable_code.keys():
            email = emailable_code[cart_item.verification_code]
        else:
            verified_sign_up = db.query(VerifiedSignUp).filter(
                VerifiedSignUp.verification_code == cart_item.verification_code).first()
            if verified_sign_up is not None:
                email = verified_sign_up.email
                emailable_code[cart_item.verification_code] = verified_sign_up.email
            else:
                unverified_sign_up = db.query(UnverifiedSignUp).filter(
                    UnverifiedSignUp.verification_code == cart_item.verification_code).first()
                if unverified_sign_up is not None:
                    email = unverified_sign_up.email
                    emailable_code[cart_item.verification_code] = unverified_sign_up.email

        if email is not None:
            items: List[int] = []
            if email in result.keys():
                items = result[email]
            items.append(cart_item.recipe_id)
            result[email] = items

    return JSONResponse(jsonable_encoder(result))
