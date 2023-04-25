from sqladmin import ModelView

from models.user import VerifiedUser, UnverifiedUser


class VerifiedUserAdmin(ModelView, model=VerifiedUser):
    column_list = [
        VerifiedUser.id,
        VerifiedUser.first_name,
        VerifiedUser.last_name,
        VerifiedUser.email,
        VerifiedUser.join_date,
        VerifiedUser.signup_date,
        VerifiedUser.signup_from,
        VerifiedUser.verification_code
    ]


class UnverifiedUserAdmin(ModelView, model=UnverifiedUser):
    column_list = [
        UnverifiedUser.id,
        UnverifiedUser.first_name,
        UnverifiedUser.last_name,
        UnverifiedUser.email,
        UnverifiedUser.signup_date,
        UnverifiedUser.signup_from,
        UnverifiedUser.zipcode,
        UnverifiedUser.verification_code
    ]
