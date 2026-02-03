import yfinance as yf
import Constants
import time

def checkConnectionestablish():
    ticker = yf.Ticker(Constants.testCompany)
    data = ticker.history(period="1d")
    print (data)

checkConnectionestablish()

def getLiveStatus(symbol):
    ticker = yf.Ticker(symbol)
    dataFrame = ticker.history(interval = "1m", period = "1d")
    return dataFrame

getLiveStatus("AAPL")