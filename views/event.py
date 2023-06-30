from sqladmin import ModelView

from models.event import Event, RecipeEvent


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
    column_default_sort = [(Event.event_timestamp, True)]


class RecipeEventAdmin(ModelView, model=RecipeEvent):
    column_list = [
        RecipeEvent.id,
        RecipeEvent.event_type,
        RecipeEvent.event_timestamp,
        RecipeEvent.code,
        RecipeEvent.referrer
    ]

    column_searchable_list = [RecipeEvent.referrer, RecipeEvent.code, RecipeEvent.event_type]
    column_sortable_list = [RecipeEvent.event_timestamp]
    column_default_sort = [(RecipeEvent.event_timestamp, True)]
