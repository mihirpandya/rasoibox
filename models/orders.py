import enum

from sqlalchemy import Column, Integer, DateTime, String, JSON, Boolean, Float, Enum

from models.base import Base


class PaymentStatusEnum(str, enum.Enum):
    INTENT = "INTENT"
    INITIATED = "INITIATED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user_facing_order_id = Column(String(100))
    order_date = Column(DateTime)
    recipes = Column(JSON)  # map<ForeignKey("recipes.id"): serving_size> of recipes ordered
    customer = Column(Integer)  # ForeignKey("customers.id")
    recipient_first_name = Column(String(100))
    recipient_last_name = Column(String(100))
    payment_status = Column(Enum(PaymentStatusEnum))
    delivered = Column(Boolean)
    delivery_date = Column(DateTime)
    order_total_dollars = Column(Float)
    order_breakdown_dollars = Column(JSON)  # map<string, float> of all line items e.g. tax, delivery, promo codes
    delivery_address = Column(JSON)  # api.orders.Address
    phone_number = Column(String(10))
    promo_codes = Column(JSON)  # list<ForeignKey("promo_codes.id")> of applied promo codes
    payment_intent = Column(String(100))  # stripe payment intent id


class Cart(Base):
    __tablename__ = "carts"
    id = Column(Integer, primary_key=True)
    verification_code = Column(String(100))
    recipe_id = Column(Integer)  # ForeignKey("recipes.id")
    serving_size = Column(Integer)


class PromoCode(Base):
    __tablename__ = "promo_codes"
    id = Column(Integer, primary_key=True)
    promo_code_name = Column(String(100))
    created_on = Column(DateTime)
    expires_on = Column(DateTime)
    number_times_redeemed = Column(Integer)
    stripe_promo_code_id = Column(String(100))
    amount_off = Column(Float)
    percent_off = Column(Float)
    redeemable_by_verification_code = Column(String(100))
