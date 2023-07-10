import enum

from sqlalchemy import Integer, Column, String, Enum, DateTime

from models.base import Base


class InvitationStatusEnum(str, enum.Enum):
    INVITED = "INVITED"
    COMPLETED = "COMPLETED"


class Invitation(Base):
    __tablename__ = "invitations"
    id = Column(Integer, primary_key=True)
    email = Column(String(100))
    referrer_verification_code = Column(String(100))
    referred_verification_code = Column(String(100))
    invitation_status = Column(Enum(InvitationStatusEnum))
    invited_on = Column(DateTime)
