import yfinance as yf
import mplfinance as mpf

# Draw candlestick chart
def showCanvas(dataFrame):
    mpf.plot(
        dataFrame,
        type="candle",
        style="yahoo",
        volume=True,
        title="AAPL Candlestick Chart",
        mav=(20, 50)
        )
