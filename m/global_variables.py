from m.config import configFile

acceptable_dc = configFile['datacenters'] if 'datacenters' in configFile else []
filterName = configFile['filterName'] if 'filterName' in configFile else ""
filterDisk = configFile['filterDisk'] if 'filterDisk' in configFile else ""
ovhSubsidiary = configFile['ovhSubsidiary'] if 'ovhSubsidiary' in configFile else "FR"
loop = configFile['loop'] if 'loop' in configFile else False
sleepsecs = configFile['sleepsecs'] if 'sleepsecs' in configFile else 60    
showPrompt = configFile['showPrompt'] if 'showPrompt' in configFile else True
showCpu = configFile['showCpu'] if 'showCpu' in configFile else True
showFqn = configFile['showFqn'] if 'showFqn' in configFile else False
showUnavailable = configFile['showUnavailable'] if 'showUnavailable' in configFile else True
showBandwidth = configFile['showBandwidth'] if 'showBandwidth' in configFile else True
fakeBuy = configFile['fakeBuy'] if 'fakeBuy' in configFile else True
coupon = configFile['coupon'] if 'coupon' in configFile else ''
autoBuyRE = configFile['auto_buy'] if 'auto_buy' in configFile else ""
autoBuyNum = configFile['auto_buy_num'] if 'auto_buy_num' in configFile else 1
autoBuyMaxPrice = configFile['auto_buy_max_price'] if 'auto_buy_max_price' in configFile else 0
autoBuyInvoicesNum = configFile['auto_buy_num_invoices'] if 'auto_buy_num_invoices' in configFile else 0
# for sending emails
email_on = configFile['email_on'] if 'email_on' in configFile else False
email_server_port = configFile['email_server_port'] if 'email_server_port' in configFile else 0
email_server_name = configFile['email_server_name'] if 'email_server_name' in configFile else ""
email_server_login = configFile['email_server_login'] if 'email_server_login' in configFile else ""
email_server_password = configFile['email_server_password'] if 'email_server_password' in configFile else ""
email_sender = configFile['email_sender'] if 'email_sender' in configFile else ""
email_receiver = configFile['email_receiver'] if 'email_receiver' in configFile else ""
email_at_startup = configFile['email_at_startup'] if 'email_at_startup' in configFile and email_on else False
email_auto_buy = configFile['email_auto_buy'] if 'email_auto_buy' in configFile and email_on else False
email_added_removed = configFile['email_added_removed'] if 'email_added_removed' in configFile and email_on else False
email_availability_monitor = configFile['email_availability_monitor'] if 'email_availability_monitor' in configFile and email_on else ""
email_catalog_monitor = configFile['email_catalog_monitor'] if 'email_catalog_monitor' in configFile and email_on else False


# Auto Buy
if autoBuyNum == 0:
    autoBuyRE = ""
autoBuyNumInit = autoBuyNum
# counters to display how auto buy are doing
autoOK = 0
autoKO = 0
autoFake = 0
