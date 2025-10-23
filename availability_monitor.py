import datetime
import sys
import time

import m.api
import m.availability
import m.monitor

availabilities=[]
previousAvailabilities=[]

while True:
    try:
        if availabilities:
            previousAvailabilities = availabilities
        availabilities = m.availability.build_availability_dict(m.api.api_url("ovh-eu"), sys.argv[1:])
        strChanged = m.monitor.avail_added_removed_Str(previousAvailabilities, availabilities)
        if strChanged:
            current_time = datetime.datetime.now()
            print(datetime.datetime.now(), " :")
            print(strChanged)
        time.sleep(30)
    except KeyboardInterrupt:
        break
