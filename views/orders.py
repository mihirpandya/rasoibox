from sqladmin import ModelView

from models.orders import Order, Cart, PromoCode


class OrderAdmin(ModelView, model=Order):
    column_list = [
        Order.id,
        Order.user_facing_order_id,
        Order.order_date,
        Order.recipes,
        Order.customer,
        Order.recipient_first_name,
        Order.recipient_last_name,
        Order.payment_status,
        Order.delivered,
        Order.order_total_dollars,
        Order.order_breakdown_dollars,
        Order.delivery_address,
        Order.phone_number,
        Order.promo_codes
    ]

    column_sortable_list = [Order.order_date]
    column_default_sort = [(Order.order_date, True)]


class CartAdmin(ModelView, model=Cart):
    column_list = [
        Cart.id,
        Cart.verification_code,
        Cart.recipe_id,
        Cart.serving_size
    ]


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
