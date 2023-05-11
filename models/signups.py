from sqlalchemy import Column, Integer, String, DateTime

from models.base import Base


class UnverifiedSignUp(Base):
    __tablename__ = "unverified_sign_ups"
    id = Column(Integer, primary_key=True)
    email = Column(String(100))
    signup_date = Column(DateTime)
    signup_from = Column(String(100))
    zipcode = Column(String(20))
    verification_code = Column(String(100))


class VerifiedSignUp(Base):
    __tablename__ = "verified_sign_ups"

    id = Column(Integer, primary_key=True)
    email = Column(String(100))
    signup_date = Column(DateTime)
    signup_from = Column(String(100))
    verify_date = Column(DateTime)
    zipcode = Column(String(20))
    verification_code = Column(String(100))
