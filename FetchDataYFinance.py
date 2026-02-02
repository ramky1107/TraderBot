import yfinance as yf
import constants

def checkConnectionestablish():
    ticker = yf.Ticker(constants.testCompany)
    data = ticker.history(period="1d")
    print (data)

checkConnectionestablish()