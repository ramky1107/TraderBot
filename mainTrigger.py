import fetchData
import drawCanvas
import constants
import time

companyName = constants.testCompany

while True:
    # dataFrame = fetchData.getLiveStatus(companySymbol= companyName)
    dataFrame = fetchData.getYFinanceLiveStatus(companySymbol= companyName)
    print (dataFrame)
    # DrawCanvas.showCanvas(dataFrame=dataFrame)
    time.sleep (0.890)
    print ("ok")