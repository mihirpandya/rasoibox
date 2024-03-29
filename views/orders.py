from sqladmin import ModelView

from models.orders import Order, Cart, PromoCode


class OrderAdmin(ModelView, model=Order):
    column_list = [
        Order.id,
        Order.user_facing_order_id,
        Order.order_date,
        Order.recipes,
        Order.customer,
        Order.verification_code,
        Order.recipient_first_name,
        Order.recipient_last_name,
        Order.recipient_email,
        Order.payment_status,
        Order.delivered,
        Order.delivery_date,
        Order.order_total_dollars,
        Order.order_breakdown_dollars,
        Order.delivery_address,
        Order.phone_number,
        Order.promo_codes,
        Order.payment_intent
    ]

    column_sortable_list = [Order.order_date]
    column_default_sort = [(Order.order_date, True)]
    column_searchable_list = [Order.recipient_first_name, Order.recipient_last_name, Order.verification_code]


class CartAdmin(ModelView, model=Cart):
    column_list = [
        Cart.id,
        Cart.verification_code,
        Cart.recipe_id,
        Cart.serving_size
    ]

    column_sortable_list = [Cart.id]
    column_default_sort = [(Cart.id, True)]
    column_searchable_list = [Cart.verification_code]


class PromoCodeAdmin(ModelView, model=PromoCode):
    column_list = [
        PromoCode.id,
        PromoCode.promo_code_name,
        PromoCode.created_on,
        PromoCode.expires_on,
        PromoCode.number_times_redeemed,
        PromoCode.stripe_promo_code_id,
        PromoCode.amount_off,
        PromoCode.percent_off,
        PromoCode.redeemable_by_verification_code
    ]

    column_sortable_list = [PromoCode.created_on]
    column_default_sort = [(PromoCode.created_on, True)]
    column_searchable_list = [PromoCode.promo_code_name, PromoCode.redeemable_by_verification_code]
