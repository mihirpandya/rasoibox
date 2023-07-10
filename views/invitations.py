from sqladmin import ModelView

from models.invitations import Invitation


class InvitationAdmin(ModelView, model=Invitation):
    column_list = [
        Invitation.id,
        Invitation.referrer_verification_code,
        Invitation.email,
        Invitation.referred_verification_code,
        Invitation.invitation_status,
        Invitation.invited_on
    ]

    column_searchable_list = [Invitation.email]
    column_sortable_list = [Invitation.invited_on]
    column_default_sort = [(Invitation.invited_on, True)]
