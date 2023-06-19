from sqlalchemy import Column, Integer, DateTime, String, JSON, Boolean, Float

from models.base import Base


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user_facing_order_id = Column(String(100))
    order_date = Column(DateTime)
    recipes = Column(JSON)  # map<ForeignKey("recipes.id"): serving_size> of recipes ordered
    customer = Column(Integer)  # ForeignKey("customers.id")
    recipient_first_name = Column(String(100))
    recipient_last_name = Column(String(100))
    delivered = Column(Boolean)
    order_total_dollars = Column(Float)
    order_breakdown_dollars = Column(JSON)  # map<string, float> of all line items e.g. tax, delivery, coupon codes
    delivery_address = Column(JSON)  # api.orders.Address
    phone_number = Column(Integer)
    coupons = Column(JSON)  # list<ForeignKey("coupons.id")> of applied coupons


class Cart(Base):
    __tablename__ = "carts"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer)  # ForeignKey("customers.id")
    recipe_id = Column(Integer)  # ForeignKey("recipes.id")
    serving_size = Column(Integer)


class Coupon(Base):
    __tablename__ = "coupons"
    id = Column(Integer, primary_key=True)
    coupon_name = Column(String(100))
    created_on = Column(DateTime)
    expires_on = Column(DateTime)
    number_times_redeemed = Column(Integer)
