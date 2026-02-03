import FetchDataYFinance
import DrawCanvas
import constants
import time

companyName = constants.testCompany

while True:
    dataFrame = FetchDataYFinance.getLiveStatus(companySymbol= companyName)
    print (dataFrame)
    DrawCanvas.showCanvas(dataFrame=dataFrame)
    time.sleep (0.890)
    print ("ok")