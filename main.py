import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import data_manager
import strategies
import plots

# Initialize the Dash App
app = dash.Dash(__name__)

# App Layout
app.layout = html.Div([
    html.H1("NIFTY 50 Algorithmic Tracker", style={'textAlign': 'center', 'color': '#ffffff'}),
    
    # The Graph Component
    dcc.Graph(id='live-chart'),
    
    # Interval Component: Triggers an update every 60 seconds (60*1000 ms)
    dcc.Interval(
        id='interval-component',
        interval=60*1000, 
        n_intervals=0
    )
], style={'backgroundColor': '#111111', 'padding': '20px'})

# Callback: Updates the graph every time the interval fires
@app.callback(Output('live-chart', 'figure'),
              [Input('interval-component', 'n_intervals')])
def update_graph_live(n):
    # 1. Fetch
    df = data_manager.fetch_market_data(period="5d", interval="1m")
    
    # 2. Process (Strategy)
    df = strategies.apply_strategies(df)
    
    # 3. Plot
    fig = plots.create_figure(df)
    
    return fig

if __name__ == '__main__':
    print("Starting Dash Server...")
    print("Open your browser and go to http://127.0.0.1:8050/")
    app.run(debug=True)