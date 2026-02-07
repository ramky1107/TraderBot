import time

import constants
import drawCanvas
import fetchDataYFinance

companyName = constants.testCompany

while True:
    dataFrame = fetchDataYFinance.getLiveStatus(companySymbol=companyName)
    print(dataFrame)
    drawCanvas.showCanvas(dataFrame=dataFrame)
    time.sleep(0.890)
    print("ok")
