from sqladmin import ModelView

from models.invitations import Invitation


class InvitationAdmin(ModelView, model=Invitation):
    column_list = [
        Invitation.id,
        Invitation.referred_by_customer_id,
        Invitation.email,
        Invitation.verification_code,
        Invitation.invitation_status
    ]

    column_searchable_list = [Invitation.email]
