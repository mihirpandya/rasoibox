from sqlalchemy import Column, Integer, String, DateTime

from models.base import Base


class CookingHistory(Base):
    __tablename__ = "cooking_history"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer)  # ForeignKey("customers.id")
    order_id = Column(String(100))  # user facing order id
    recipe_id = Column(Integer)  # ForeignKey("recipes.id")
    cook_date = Column(DateTime)
