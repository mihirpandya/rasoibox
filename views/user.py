from sqladmin import ModelView

from models.signups import VerifiedSignUp, UnverifiedSignUp, DeliverableZipcode


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

    column_searchable_list = [VerifiedSignUp.email, VerifiedSignUp.zipcode, VerifiedSignUp.verification_code]
    column_sortable_list = [VerifiedSignUp.signup_date, VerifiedSignUp.verify_date, VerifiedSignUp.zipcode]
    column_default_sort = [(VerifiedSignUp.verify_date, True)]


class UnverifiedUserAdmin(ModelView, model=UnverifiedSignUp):
    column_list = [
        UnverifiedSignUp.id,
        UnverifiedSignUp.email,
        UnverifiedSignUp.signup_date,
        UnverifiedSignUp.signup_from,
        UnverifiedSignUp.zipcode,
        UnverifiedSignUp.verification_code
    ]

    column_searchable_list = [UnverifiedSignUp.email, UnverifiedSignUp.zipcode]
    column_sortable_list = [UnverifiedSignUp.signup_date, UnverifiedSignUp.zipcode]
    column_default_sort = [(UnverifiedSignUp.signup_date, True)]


class DeliverableZipcodeAdmin(ModelView, model=DeliverableZipcode):
    column_list = [
        DeliverableZipcode.id,
        DeliverableZipcode.zipcode,
        DeliverableZipcode.delivery_start_date
    ]
