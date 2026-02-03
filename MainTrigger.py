import FetchDataYFinance
import DrawCanvas
import Constants
import time

companyName = Constants.testCompany

while True:
    dataFrame = FetchDataYFinance.getLiveStatus(symbol= companyName)
    DrawCanvas.showCanvas(dataFrame=dataFrame)
    time.sleep (0.890)
    print ("ok")