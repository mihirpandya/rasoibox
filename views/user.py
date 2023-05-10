from sqladmin import ModelView

from models.signups import VerifiedSignUp, UnverifiedSignUp


class VerifiedUserAdmin(ModelView, model=VerifiedSignUp):
    column_list = [
        VerifiedSignUp.id,
        VerifiedSignUp.email,
        VerifiedSignUp.verify_date,
        VerifiedSignUp.signup_date,
        VerifiedSignUp.signup_from,
        VerifiedSignUp.zipcode,
        VerifiedSignUp.verification_code
    ]


class UnverifiedUserAdmin(ModelView, model=UnverifiedSignUp):
    column_list = [
        UnverifiedSignUp.id,
        UnverifiedSignUp.email,
        UnverifiedSignUp.signup_date,
        UnverifiedSignUp.signup_from,
        UnverifiedSignUp.zipcode,
        UnverifiedSignUp.verification_code
    ]
