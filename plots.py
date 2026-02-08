import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_figure(df, ticker="^NSEI"):
    """
    Generates the Plotly Figure with continuous Candle chart (no gaps).
    Includes Price, RSI, and Volume subplots.
    """
    if df.empty:
        return go.Figure()

    # Create subplots: Row 1 for Price, Row 2 for RSI, Row 3 for Volume
    fig = make_subplots(
        rows=3, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03,
        subplot_titles=(f'{ticker} Price', 'RSI (14)', 'Volume'),
        row_heights=[0.5, 0.25, 0.25]
    )

    # 1. Candlestick Chart
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='OHLC'
    ), row=1, col=1)

    # 2. 20-Day Moving Average
    if 'SMA_20' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['SMA_20'],
            mode='lines',
            line=dict(color='orange', width=2),
            name='20-Day MA'
        ), row=1, col=1)

    # 3. RSI Chart
    if 'RSI' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['RSI'],
            mode='lines',
            line=dict(color='purple', width=2),
            name='RSI'
        ), row=2, col=1)
        
        # Add overbought/oversold reference lines
        fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=2, col=1)
        
        # Update RSI y-axis range
        fig.update_yaxes(range=[0, 100], row=2, col=1)

    # 4. Volume Chart
    fig.add_trace(go.Bar(
        x=df.index,
        y=df['Volume'],
        name='Volume',
        marker_color='lightblue'
    ), row=3, col=1)

    # Remove Time Gaps (weekends for daily data)
    fig.update_xaxes(
        rangebreaks=[
            dict(bounds=["sat", "mon"]),  # Hide Weekends
        ]
    )

    # Layout Customization
    last_price = df['Close'].iloc[-1] if not df.empty else 0
    fig.update_layout(
        title=dict(
            text=f"{ticker} - Last: {last_price:.2f}",
            font=dict(size=16, family='Ubuntu, sans-serif'),
            x=0.01,
            xanchor='left'
        ),
        yaxis_title='Price',
        yaxis2_title='RSI',
        yaxis3_title='Volume',
        template='plotly_dark',
        xaxis_rangeslider_visible=False,
        height=None,  # Let container control height
        margin=dict(l=60, r=20, t=40, b=40),
        hovermode='x unified',
        paper_bgcolor='#131722',
        plot_bgcolor='#131722',
        font=dict(family='Ubuntu, sans-serif', color='#D1D4DC'),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="right",
            x=1,
            font=dict(size=12)
        )
    )

    return fig