from datetime import datetime, timedelta

from m.api import client

# ----------------- SHOW UNPAID ORDERS --------------------------------------------------------
def unpaidOrders():
    # Get today's date
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    # Calculate the date 14 days ago
    date_14_days_ago = today - timedelta(days=14)

    params = {}
    params['date.from'] = date_14_days_ago.strftime('%Y-%m-%d')
    params['date.to'] = tomorrow.strftime('%Y-%m-%d')

    API_orders = client.get("/me/order/", **params)

    orderList = []

    print("Building list of unpaid orders. Please wait.")

    for orderId in API_orders:
        orderStatus = client.get("/me/order/{0}/status/".format(orderId))
        if orderStatus == 'notPaid':
            details = client.get("/me/order/{0}/details/".format(orderId))
            for detailId in details:
                orderDetail = client.get("/me/order/{0}/details/{1}".format(orderId, detailId))
                if orderDetail['domain'] == '*001' and orderDetail['detailType'] == "DURATION":
                    description = orderDetail['description'].split('|')[0].split(' ')[0]
                    location = orderDetail['description'].split('-')[-2][-4:]
                    theOrder = client.get("/me/order/{0}/".format(orderId))
                    orderURL = theOrder['url']
                    orderDate = theOrder['expirationDate'].split('T')[0]
                    orderList.append({
                                    'orderId' : orderId,
                                    'description' : description,
                                    'location' : location,
                                    'url' : orderURL,
                                    'date' : orderDate})

    for order in orderList:
        print (str(orderList.index(order)).ljust(4) + "| "
            + order['description'].ljust(10) + "| "
            + order['location']  + "| "
            + order['date'])

    continueLoop = True
    while continueLoop:
        sChoice = input("Which one? ")
        if sChoice.isdigit():
            choice = int (sChoice)
            if choice >= len(orderList):
                continueLoop = False
            else:
                print ("URL: " + orderList[choice]['url'])
        else:
            continueLoop = False