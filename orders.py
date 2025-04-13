import ovh
import sys
import yaml
from datetime import datetime, timedelta

configFile = {}
try:
    configFile = yaml.safe_load(open('conf.yaml', 'r'))
except Exception as e:
    print("Error with config.yaml")
    print(e)
    sys.exit("Bye now.")

# --- Create the API client -----------------
if 'APIEndpoint' not in configFile:
    print("APIEndpoint is mandatory in config file.")
    print("It should look like 'ovh-eu', 'ovh-us', 'ovh-ca'")
    print("See https://github.com/ovh/python-ovh?tab=readme-ov-file#1-create-an-application")
    sys.exit("Bye now.")
else:
    api_endpoint = configFile['APIEndpoint']

if 'APIKey' not in configFile or 'APISecret' not in configFile:
    print("APIKey and APISecret are mandatory in config file.")
    print("You need to create an application key!")
    print("See https://github.com/ovh/python-ovh?tab=readme-ov-file#1-create-an-application")
    print("Once you have the key and secret for your endpoint, fill APIKey and APISecret.")
    sys.exit("Bye now.")
else:
    api_key = configFile['APIKey']
    api_secret = configFile['APISecret']

if 'APIConsumerKey' not in configFile:
    print("You need a consumer key in the config file.")
    print("Let's try to get you one with full access.")
    ck_client = ovh.Client(endpoint=api_endpoint,
                           application_key=api_key,
                           application_secret=api_secret)
    ck = ck_client.new_consumer_key_request()
    ck.add_recursive_rules(ovh.API_READ_WRITE, "/")
    validation = ck.request()
    print("Please visit %s to authenticate" % validation['validationUrl'])
    input("and press Enter to continue...")
    print("Ok", ck_client.get('/me')['firstname'])
    print("Your APIConsumerKey is '%s'" % validation['consumerKey'])
    print("Add it to the config file and try again.")
    sys.exit("Bye now.")        
else:
    api_ck = configFile['APIConsumerKey']

client = ovh.Client(endpoint=api_endpoint,
                    application_key=api_key,
                    application_secret=api_secret,
                    consumer_key=api_ck)

# Get today's date
today = datetime.now()
# Calculate the date 14 days ago
date_14_days_ago = today - timedelta(days=14)

# Print the result
params = {}
params['date.from'] = date_14_days_ago.strftime('%Y-%m-%d')
params['date.to'] = today.strftime('%Y-%m-%d')

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
                description = orderDetail['description']
                theOrder = client.get("/me/order/{0}/".format(orderId))
                orderURL = theOrder['url']
                orderList.append({
                                  'orderId' : orderId,
                                  'description' : description,
                                  'url' : orderURL})

for order in orderList:
    print (str(orderList.index(order)).ljust(4) + "| "
           + order['description'])

sChoice = "0"
while sChoice.isdigit():
    sChoice = input("Which one? ")
    if sChoice.isdigit():
        choice = int (sChoice)
        if choice >= len(orderList):
            sys.exit("You had one job.")
        print ("URL: " + orderList[choice]['url'])
