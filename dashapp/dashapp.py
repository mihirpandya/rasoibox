import logging

import dash
import plotly.graph_objs as go
from dash import dcc, html
from dash.dependencies import Input, Output
from sqlalchemy.orm import Session

from models.event import Event

# select date_format(event_timestamp,'%Y-%m-%d %H'), count(1) from events group by 1;
# select date_format(event_timestamp,'%Y-%m-%d %H-%I'), count(1) from events group by 1;
# select distinct event_type from events;

logger = logging.getLogger("rasoibox")


def update_verified_signups_graph(db: Session):
    statement = "select date_format(verify_date, '%Y-%m-%d'), count(1) from verified_sign_ups group by 1"
    data = db.execute(statement).all()
    timestamps = [x[0] for x in data]
    signups_count = [x[1] for x in data]
    print(timestamps)
    print(signups_count)
    return {
        'data': [{
            'x': timestamps,
            'y': signups_count,
            'line': {
                'width': 3,
                'shape': 'spline'
            }
        }],
        'layout': {
            'margin': {
                'l': 30,
                'r': 20,
                'b': 30,
                't': 20
            }
        }
    }


def create_dash_app(db: Session, requests_pathname_prefix: str = None) -> dash.Dash:
    event_types_rows = db.query(Event.event_type).distinct(Event.event_type).all()
    event_types = [x[0] for x in event_types_rows]

    app = dash.Dash(__name__, requests_pathname_prefix=requests_pathname_prefix)

    app.scripts.config.serve_locally = False
    dcc._js_dist[0]['external_url'] = 'https://cdn.plot.ly/plotly-basic-latest.min.js'

    events_graph_div = html.Div([
        html.H1('Site Events'),
        dcc.Dropdown(
            id='events-dropdown',
            options=[{'label': x, 'value': x} for x in event_types],
            value=event_types[0]
        ),
        dcc.Graph(id='events-graph')
    ], className="events")

    verified_signups_graph_div = html.Div([
        html.H1('Verified Sign Ups'),
        dcc.Graph(id='verified-signups-graph', figure=update_verified_signups_graph(db))
    ], className="verified_signups")

    app.layout = html.Div([verified_signups_graph_div, events_graph_div], className="container")

    @app.callback(Output('events-graph', 'figure'),
                  [Input('events-dropdown', 'value')])
    def update_events_graph(selected_dropdown_value):
        statement = "select date_format(event_timestamp,'%Y-%m-%d %H-%I'), count(1) " \
                    "from events where event_type=\"{}\" group by 1".format(selected_dropdown_value)
        data = db.execute(statement).all()
        timestamps = [x[0] for x in data]
        event_count = [x[1] for x in data]
        return {
            'data': [{
                'x': timestamps,
                'y': event_count,
                'line': {
                    'width': 3,
                    'shape': 'spline'
                }
            }],
            'layout': {
                'margin': {
                    'l': 30,
                    'r': 20,
                    'b': 30,
                    't': 20
                }
            }
        }

    return app
