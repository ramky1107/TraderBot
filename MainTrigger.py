import FetchDataYFinance
import DrawCanvas
import Constants
import time

companyName = Constants.testCompany

while True:
    dataFrame = FetchDataYFinance.getLiveStatus(companySymbol= companyName)
    print (dataFrame)
    DrawCanvas.showCanvas(dataFrame=dataFrame)
    time.sleep (0.890)
    print ("ok")