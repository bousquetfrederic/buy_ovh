import ovh
import time

__all__ = ['api_url','build_cart', 'checkout_cart', 'get_unpaid_orders', 'get_consumer_key', 'login', 'is_logged_in']

# --- Exceptions ----------------------------
class NotLoggedIn(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

# --- Variables -----------------------------
client = None

# --- What is the URL of the API? --------------------------------------------------------------
def api_url(endpoint):
    if endpoint == 'ovh-ca':
        return "https://ca.api.ovh.com/v1/"
    elif endpoint == 'ovh-us':
        return "https://api.us.ovhcloud.com/v1/"
    else:
        return "https://eu.api.ovh.com/v1/"

# ---------------- ARE WE LOGGED IN? -----------------------------------------------------------
def is_logged_in():
    return client != None

# ---------------- LOGIN TO THE API ------------------------------------------------------------
def login(endpoint, application_key, application_secret, consumer_key):
    global client
    try:
        client = ovh.Client(endpoint=endpoint,
                            application_key=application_key,
                            application_secret=application_secret,
                            consumer_key=consumer_key)
        return True
    except Exception as e:
        print("Failed to login.")
        print(e)
        return False

# ---------------- GET A CONSUMER KEY ----------------------------------------------------------
def get_consumer_key(endpoint, application_key, application_secret):
    global client
    try:
        client = ovh.Client(endpoint=endpoint,
                            application_key=application_key,
                            application_secret=application_secret)

        ck = client.new_consumer_key_request()
        ck.add_recursive_rules(ovh.API_READ_WRITE, '/')
        validation = ck.request()

        print("Please visit %s to authenticate" % validation['validationUrl'])
        input("and press Enter to continue...")

        return validation['consumerKey']
    except Exception as e:
        print("Failed to get consumer key.")
        print(e)
        return "nokey"

# ---------------- BUILD THE CART --------------------------------------------------------------
def build_cart(plan, ovhSubsidiary, coupon, fake=False):
    if fake:
        print("Fake cart!")
        time.sleep(1)
        return 0
    elif client == None:
        raise NotLoggedIn("Need to be logged in to build the cart.")

    # make a cart
    cart = client.post("/order/cart", ovhSubsidiary=ovhSubsidiary)
    cartId = cart.get("cartId")
    client.post("/order/cart/{0}/assign".format(cartId))
    # add the server
    result = client.post(
                         f'/order/cart/{cart.get("cartId")}/eco',
                         duration = "P1M",
                         planCode = plan['planCode'],
                         pricingMode = "default",
                         quantity = 1
                        )
    itemId = result['itemId']

    # add options
    result = client.post(
                         f'/order/cart/{cartId}/eco/options',
                         duration = "P1M",
                         itemId = itemId,
                         planCode = plan['memory'],
                         pricingMode = "default",
                         quantity = 1
                        )
    result = client.post(
                         f'/order/cart/{cartId}/eco/options',
                         itemId = itemId,
                         duration = "P1M",
                         planCode = plan['storage'],
                         pricingMode = "default",
                         quantity = 1
                        )
    result = client.post(
                         f'/order/cart/{cartId}/eco/options',
                         itemId = itemId,
                         duration = "P1M",
                         planCode = plan['bandwidth'],
                         pricingMode = "default",
                         quantity = 1
                        )
    if plan['vrack'] != 'none':
        result = client.post(
                            f'/order/cart/{cartId}/eco/options',
                            itemId = itemId,
                            duration = "P1M",
                            planCode = plan['vrack'],
                            pricingMode = "default",
                            quantity = 1
                            )

    # add configuration
    result = client.post(
                         f'/order/cart/{cartId}/item/{itemId}/configuration',
                         label = "dedicated_datacenter",
                         value = plan['datacenter']
                         )
    result = client.post(
                         f'/order/cart/{cartId}/item/{itemId}/configuration',
                         label = "dedicated_os",
                         value = "none_64.en"
                         )
    if plan['datacenter'] in ["bhs", "syd", "sgp"]:
        myregion = "canada"
    else:
        myregion = "europe"
    result = client.post(
                         f'/order/cart/{cartId}/item/{itemId}/configuration',
                         label = "region",
                         value = myregion
                         )

    # add coupon
    if coupon:
        result = client.post(f'/order/cart/{cartId}/coupon',
                             label = "coupon",
                             value = coupon)

    return cartId

# ---------------- CHECKOUT THE CART ---------------------------------------------------------
def checkout_cart(cartId, buyNow, fake=False):
    if fake:
        print("Fake buy! Now: " + str(buyNow))
        time.sleep(2)
        return
    elif client == None:
        raise NotLoggedIn("Need to be logged in to check out the cart.")

    # this is it, we checkout the cart!
    result = client.post(f'/order/cart/{cartId}/checkout',
                         autoPayWithPreferredPaymentMethod=buyNow,
                         waiveRetractationPeriod=buyNow
                        )


# ----------------- ORDERS --------------------------------------------------------------------
def get_unpaid_orders(date_from, date_to, printMessage=False):
    if client == None:
        raise NotLoggedIn("Need to be logged in to get unpaid orders.")
    params = {}
    params['date.from'] = date_from.strftime('%Y-%m-%d')
    params['date.to'] = date_to.strftime('%Y-%m-%d')
    API_orders = client.get("/me/order/", **params)
    orderList = []
    if printMessage:
        print("Building list of unpaid orders. Please wait.")
    for orderId in API_orders:
        if printMessage:
            print("(" + str(API_orders.index(orderId)+1) + "/" + str(len(API_orders)) + ")", end="\r", flush=True)
        if client.get("/me/order/{0}/status/".format(orderId)) == 'notPaid':
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
    return orderList
