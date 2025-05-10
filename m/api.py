import ovh
import time

import m.config
import m.email
import m.global_variables as GV

# --- Create the API client -----------------
if 'APIEndpoint' not in m.config.configFile:
    print("APIEndpoint is mandatory in config file.")
    print("It should look like 'ovh-eu', 'ovh-us', 'ovh-ca'")
    print("See https://github.com/ovh/python-ovh?tab=readme-ov-file#1-create-an-application")
    sys.exit("Bye now.")
else:
    api_endpoint = m.config.configFile['APIEndpoint']

if 'APIKey' not in m.config.configFile or 'APISecret' not in m.config.configFile:
    print("APIKey and APISecret are mandatory in config file.")
    print("You need to create an application key!")
    print("See https://github.com/ovh/python-ovh?tab=readme-ov-file#1-create-an-application")
    print("Once you have the key and secret for your endpoint, fill APIKey and APISecret.")
    sys.exit("Bye now.")
else:
    api_key = m.config.configFile['APIKey']
    api_secret = m.config.configFile['APISecret']

if 'APIConsumerKey' not in m.config.configFile:
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
    api_ck = m.config.configFile['APIConsumerKey']

client = ovh.Client(endpoint=api_endpoint,
                    application_key=api_key,
                    application_secret=api_secret,
                    consumer_key=api_ck)

# ---------------- BUILD THE CART --------------------------------------------------------------
def buildCart(plan):
    if GV.fakeBuy:
        print("Fake cart!")
        time.sleep(1)
        return 0

    # make a cart
    cart = client.post("/order/cart", ovhSubsidiary=GV.ovhSubsidiary)
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
    if GV.coupon:
        result = client.post(f'/order/cart/{cartId}/coupon',
                             label = "coupon",
                             value = coupon)

    return cartId

# ---------------- CHECKOUT THE CART ---------------------------------------------------------
def checkoutCart(cartId, buyNow, autoMode):
    if GV.fakeBuy:
        print("Fake buy! Now: " + str(buyNow) + ", Auto: " + str(autoMode))
        time.sleep(2)
        if autoMode:
            GV.autoFake += 1
        return

    # this is it, we checkout the cart!
    result = client.post(f'/order/cart/{cartId}/checkout',
                         autoPayWithPreferredPaymentMethod=buyNow,
                         waiveRetractationPeriod=buyNow
                        )
    if autoMode:
        GV.autoOK += 1

# ----------------- BUY SERVER ----------------------------------------------------------------
def buyServer(plan, buyNow, autoMode):
    if autoMode:
        strAuto = "   -Auto Mode-"
    else:
        strAuto = ""
    if buyNow:
        strBuyNow = "buy now a "
    else:
        strBuyNow = "get an invoice for a "
    strBuy = strBuyNow + plan['invoiceName'] + " in " + plan['datacenter'] + "."
    print("Let's " + strBuy + strAuto)
    try:
        checkoutCart(buildCart(plan), buyNow, autoMode)
        if autoMode and GV.email_auto_buy:
            m.email.sendAutoBuyEmail("SUCCESS: " + strBuy)
    except Exception as e:
        print("Not today.")
        print(e)
        if autoMode and GV.email_auto_buy:
            m.email.sendAutoBuyEmail("FAILED: " + strBuy)
        if autoMode:
            GV.autoKO += 1
        time.sleep(3)

