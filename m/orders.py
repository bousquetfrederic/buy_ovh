from datetime import datetime, timedelta

import m.api
import m.print

__all__ = ['unpaid_orders']

# ----------------- SHOW UNPAID ORDERS --------------------------------------------------------
def unpaid_orders(printMessage=False):
    # Get today's date
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    # Calculate the date 14 days ago
    date_14_days_ago = today - timedelta(days=14)

    unpaidOrderList = []
    try:
        unpaidOrderList = m.api.get_unpaid_orders(date_14_days_ago, tomorrow, printMessage)
    except KeyboardInterrupt:
        pass
    m.print.print_orders(unpaidOrderList)

    while True:
        sChoice = input("Which one? ")
        if not sChoice.isdigit() or int (sChoice) >= len(unpaidOrderList):
            break
        choice = int (sChoice)
        print ("URL: " + unpaidOrderList[choice]['url'])