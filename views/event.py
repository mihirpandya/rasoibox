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
