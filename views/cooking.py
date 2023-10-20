from sqladmin import ModelView

from models.cooking import CookingHistory


class CookingHistoryAdmin(ModelView, model=CookingHistory):
    column_list = [
        CookingHistory.id,
        CookingHistory.customer_id,
        CookingHistory.order_id,
        CookingHistory.recipe_id,
        CookingHistory.cook_date
    ]

    column_sortable_list = [CookingHistory.cook_date]
    column_default_sort = [(CookingHistory.cook_date, True)]
    column_searchable_list = [CookingHistory.customer_id, CookingHistory.recipe_id, CookingHistory.order_id]
