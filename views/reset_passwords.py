from sqladmin import ModelView

from models.reset_passwords import ResetPassword


class ResetPasswordsAdmin(ModelView, model=ResetPassword):
    column_list = [
        ResetPassword.id,
        ResetPassword.email,
        ResetPassword.reset_date,
        ResetPassword.reset_code,
        ResetPassword.reset_complete
    ]
    column_sortable_list = [ResetPassword.reset_date]
