from datetime import datetime, timedelta

import m.api
import m.print

__all__ = ['unpaid_orders', 'undelivered_orders']

# ----------------- SHOW UNPAID ORDERS --------------------------------------------------------
def unpaid_orders(printMessage=False):
    # Get today's date
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    # Calculate the date 14 days ago
    date_14_days_ago = today - timedelta(days=14)

    unpaidOrderList = []
    try:
        unpaidOrderList = m.api.get_orders_per_status(date_14_days_ago, tomorrow, ['notPaid'], printMessage)
    except KeyboardInterrupt:
        pass
    m.print.print_orders(unpaidOrderList, True)

    while True:
        sChoice = input("Which one? ")
        if not sChoice.isdigit() or int (sChoice) >= len(unpaidOrderList):
            break
        choice = int (sChoice)
        print ("URL: " + unpaidOrderList[choice]['url'])

# ----------------- SHOW UNDELIVERED ORDERS --------------------------------------------------------
def undelivered_orders(printMessage=False):
    # Get today's date
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    # Calculate the date 14 days ago
    date_30_days_ago = today - timedelta(days=30)

    undeliveredOrderList = []
    try:
        undeliveredOrderList = m.api.get_orders_per_status(date_30_days_ago, tomorrow, ['delivering'], printMessage)
    except KeyboardInterrupt:
        pass
    m.print.print_orders(undeliveredOrderList, True)

    while True:
        sChoice = input("Which one? ")
        if not sChoice.isdigit() or int (sChoice) >= len(undeliveredOrderList):
            break
        choice = int (sChoice)
        print ("URL: " + undeliveredOrderList[choice]['url'])
