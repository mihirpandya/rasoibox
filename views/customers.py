from sqladmin import ModelView

from models.customers import Customer


class CustomerAdmin(ModelView, model=Customer):
    column_list = [
        Customer.id,
        Customer.first_name,
        Customer.last_name,
        Customer.email,
        Customer.verified,
        Customer.join_date,
        Customer.hashed_password
    ]

    column_sortable_list = [Customer.join_date]
    column_default_sort = [(Customer.join_date, True)]
