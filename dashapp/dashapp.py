from typing import List

import dash
import pandas as pd
from dash import dcc, html
from dash.dependencies import Input, Output
from sqlalchemy.orm import Session

from main import get_db
from models.event import Event


# select date_format(event_timestamp,'%Y-%m-%d %H'), count(1) from events group by 1;


def create_dash_app(requests_pathname_prefix: str = None) -> dash.Dash:
    db: Session = get_db()
    event_types: List[str] = db.query(Event).distinct(Event.event_type).all()
    df = pd.read_csv('https://raw.githubusercontent.com/plotly/datasets/master/hello-world-stock.csv')

    app = dash.Dash(__name__, requests_pathname_prefix=requests_pathname_prefix)

    app.scripts.config.serve_locally = False
    dcc._js_dist[0]['external_url'] = 'https://cdn.plot.ly/plotly-basic-latest.min.js'

    app.layout = html.Div([
        html.H1('Stock Tickers'),
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
        dff = df[df['Stock'] == selected_dropdown_value]
        return {
            'data': [{
                'x': dff.Date,
                'y': dff.Close,
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
