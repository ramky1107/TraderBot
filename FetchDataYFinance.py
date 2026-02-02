import yfinance as yf
import constants
import time

def checkConnectionestablish():
    ticker = yf.Ticker(constants.testCompany)
    data = ticker.history(period="1d")
    print (data)

checkConnectionestablish()

def getLiveStatus(symbol):
    ticker = yf.Ticker(symbol)
    while True:
        data = ticker.history(interval = "1m", period = "1d")
        print (data)
        time.sleep(1000 * 60)

getLiveStatus("AAPL")