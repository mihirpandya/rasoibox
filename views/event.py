from sqladmin import ModelView

from models.event import Event


class EventAdmin(ModelView, model=Event):
    column_list = [
        Event.id,
        Event.event_type,
        Event.event_timestamp,
        Event.code,
        Event.referrer
    ]

    column_searchable_list = [Event.referrer, Event.code, Event.event_type]
    column_sortable_list = [Event.event_timestamp]
