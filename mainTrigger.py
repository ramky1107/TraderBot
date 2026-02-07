import fetchData
import drawCanvas
import constants
import time

while True:
    # dataFrame = fetchData.getLiveStatus(companySymbol= constants.testCompany)
    dataFrame = fetchData.getYFinanceLiveStatus(companyName = constants.testCompanyYFinance, duration = constants.duration, interval = constants.interval)
    print(dataFrame)
    drawCanvas.showCanvas(dataFrame=dataFrame)
    time.sleep (0.890)