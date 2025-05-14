from datetime import datetime, timedelta

import m.api
import m.print

# ----------------- SHOW UNPAID ORDERS --------------------------------------------------------
def unpaidOrders(printMessage=False):
    # Get today's date
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    # Calculate the date 14 days ago
    date_14_days_ago = today - timedelta(days=14)

    unpaidOrderList = []
    try:
        unpaidOrderList = m.api.getUnpaidOrders(date_14_days_ago, tomorrow, printMessage)
    except KeyboardInterrupt:
        pass
    m.print.printOrders(unpaidOrderList)

    while True:
        sChoice = input("Which one? ")
        if not sChoice.isdigit() or int (sChoice) >= len(unpaidOrderList):
            break
        choice = int (sChoice)
        print ("URL: " + unpaidOrderList[choice]['url'])