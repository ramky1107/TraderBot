import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import data_manager
import strategies
import plots

# Initialize the Dash App with external assets
app = dash.Dash(__name__, assets_folder='assets')

# App Layout - TradingView Style
app.layout = html.Div([
    # Compact Toolbar
    html.Div([
        html.Label("Ticker:", className='toolbar-label'),
        dcc.Input(
            id='ticker-input',
            type='text',
            value='^NSEI',
            placeholder='Enter symbol...',
            className='ticker-input'
        ),
        html.Button('Fetch Data', id='submit-button', n_clicks=0, className='fetch-button')
    ], className='toolbar-container'),
    
    # Chart Container
    html.Div([
        dcc.Graph(
            id='live-chart',
            config={'displayModeBar': False},
            style={'height': '100%'}
        )
    ], className='chart-container'),
    
    # Interval Component: Auto-refresh every 5 minutes
    dcc.Interval(
        id='interval-component',
        interval=300*1000, 
        n_intervals=0
    )
], style={'height': '100vh', 'display': 'flex', 'flexDirection': 'column'})

# Callback: Updates the graph when button is clicked or interval fires
@app.callback(
    Output('live-chart', 'figure'),
    [Input('submit-button', 'n_clicks'),
     Input('interval-component', 'n_intervals')],
    [State('ticker-input', 'value')]
)
def update_graph_live(n_clicks, n_intervals, ticker):
    # Use default ticker if empty
    if not ticker or ticker.strip() == '':
        ticker = '^NSEI'
    
    # 1. Fetch 60 days of daily data
    df = data_manager.fetch_market_data(ticker=ticker, period="60d", interval="1d")
    
    # 2. Process (Strategy)
    df = strategies.apply_strategies(df)
    
    # 3. Plot
    fig = plots.create_figure(df, ticker=ticker)
    
    return fig

if __name__ == '__main__':
    print("Starting Dash Server...")
    print("Open your browser and go to http://127.0.0.1:8050/")
    app.run(debug=True, host='0.0.0.0', port=8050)