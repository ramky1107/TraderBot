import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_figure(df):
    """
    Generates the Plotly Figure with Candlestick and Volume subplots.
    """
    if df.empty:
        return go.Figure()

    # Create subplots: Row 1 for Price, Row 2 for Volume
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03, 
        subplot_titles=('NIFTY 50 Price', 'Volume'),
        row_heights=[0.7, 0.3]
    )

    # 1. Candlestick Chart (Main)
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='OHLC'
    ), row=1, col=1)

    # 2. Moving Average (Strategy)
    if 'SMA_20' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['SMA_20'],
            mode='lines',
            line=dict(color='orange', width=1.5),
            name='20 SMA'
        ), row=1, col=1)

    # 3. Volume Chart (Bottom)
    fig.add_trace(go.Bar(
        x=df.index,
        y=df['Volume'],
        name='Volume',
        marker_color='lightblue'
    ), row=2, col=1)

    # Layout Customization
    fig.update_layout(
        title=f"Live NIFTY 50 Tracker (Last Price: {df['Close'].iloc[-1]:.2f})",
        yaxis_title='Price',
        template='plotly_dark',
        xaxis_rangeslider_visible=False, # Hide the bottom slider
        height=700,
        hovermode='x unified' # Shows all data points for that time on hover
    )

    return fig