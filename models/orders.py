from sqlalchemy import Column, Integer, DateTime, String, JSON, Boolean, Float

from models.base import Base


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    order_date = Column(DateTime)
    recipes = Column(JSON)  # map<ForeignKey("recipes.id"): serving_size> of recipes ordered
    ordered_by = Column(Integer)  # ForeignKey("customers.id")
    delivered = Column(Boolean)
    order_total_dollars = Column(Float)
    order_breakdown_dollars = Column(JSON)  # map<string, float> of all line items e.g. tax, delivery, coupon codes
    delivery_address = Column(String(1000))
    phone_number = Column(Integer)
