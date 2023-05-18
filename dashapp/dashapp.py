import logging

import dash
from dash import dcc, html
from dash.dependencies import Input, Output
from sqlalchemy.orm import Session

from models.event import Event

# select date_format(event_timestamp,'%Y-%m-%d %H'), count(1) from events group by 1;
# select date_format(event_timestamp,'%Y-%m-%d %H-%I'), count(1) from events group by 1;
# select distinct event_type from events;

logger = logging.getLogger("rasoibox")


def create_dash_app(db: Session, requests_pathname_prefix: str = None) -> dash.Dash:
    event_types_rows = db.query(Event.event_type).distinct(Event.event_type).all()
    print(event_types_rows)
    event_types = [x[0] for x in event_types_rows]

    app = dash.Dash(__name__, requests_pathname_prefix=requests_pathname_prefix)

    app.scripts.config.serve_locally = False
    dcc._js_dist[0]['external_url'] = 'https://cdn.plot.ly/plotly-basic-latest.min.js'

    app.layout = html.Div([
        html.H1('Rasoi Box Events'),
        dcc.Dropdown(
            id='my-dropdown',
            options=[{'label': x, 'value': x} for x in event_types],
            value=event_types[0]
        ),
        dcc.Graph(id='my-graph')
    ], className="container")

    @app.callback(Output('my-graph', 'figure'),
                  [Input('my-dropdown', 'value')])
    def update_graph(selected_dropdown_value):
        statement = "select date_format(event_timestamp,'%Y-%m-%d %H-%I'), count(1) " \
                    "from events where event_type=\"{}\" group by 1".format(selected_dropdown_value)
        data = db.execute(statement).all()
        print(data)
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
