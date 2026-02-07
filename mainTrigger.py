import fetchData
import drawCanvas
import constants
import time

import constants
import drawCanvas
import fetchDataYFinance

companyName = constants.testCompany

while True:
    # dataFrame = FetchData.getLiveStatus(companySymbol= companyName)
    dataFrame = FetchData.getYFinanceLiveStatus(companySymbol= companyName)
    print (dataFrame)
    DrawCanvas.showCanvas(dataFrame=dataFrame)
    time.sleep (0.890)
    print ("ok")