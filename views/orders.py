from sqladmin import ModelView

from models.orders import Order, Cart, Coupon


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
        Order.coupons
    ]


class CartAdmin(ModelView, model=Cart):
    column_list = [
        Cart.id,
        Cart.customer_id,
        Cart.recipe_id,
        Cart.serving_size
    ]


class CouponAdmin(ModelView, model=Coupon):
    column_list = [
        Coupon.id,
        Coupon.coupon_name,
        Coupon.created_on,
        Coupon.expires_on,
        Coupon.number_times_redeemed
    ]
