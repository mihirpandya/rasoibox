import enum

from sqlalchemy import Integer, Column, String, Enum

from models.base import Base


class InvitationStatusEnum(str, enum.Enum):
    INVITED = "INVITED"
    COMPLETED = "COMPLETED"


class Invitation(Base):
    __tablename__ = "invitations"
    id = Column(Integer, primary_key=True)
    referred_by_customer_id = Column(Integer)
    email = Column(String(100))
    verification_code = Column(String(100))
    invitation_status = Column(Enum(InvitationStatusEnum))
