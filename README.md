# buy_ovh.py
Python script that uses the OVH API and their Python helper. See here: https://github.com/ovh/python-ovh

Install the dependencies:
```
pip install -r requirements.txt
```

The main program is buy_ovh.py.

There is a conf file that you need to make, conf.yaml, where you can define stuff. There is an example file provided. The file explains all the parameters.

In there you at least need the following for the connection to the API: endpoint, api key and secret. You can read about them at the python-ovh repo (above). A consumer key is also needed but the script will help you generate one if you have not got one.
To know what parameter does what, read the code.

It's recommended to have at least a filter on the server name (or plan code) otherwise the list will be huge.

The colour coding is in the code. Red is unavailable. Green and yellow are available. Etc.

Once you have chosen a server that happens to be available, press CTRL-C to stop the infinite loop (if you have defined 'loop' to true).
Then you can chose which server you want, and if you want to generate the invoice or pay with your favourite method.

You can also toggle the display of some stuff or the auto-loop, and change or empty the filters.

The script can also show you a list of your unpaid orders and provide an URL if you want to pay for one.

If you end up buying a 600€ server, it's not the script fault, it's yours, because this is just a random python script you found on the internet.

I have only tested with OVH France.

# Donations
If you would like to make a small donation because this script helped you get the server of your dreams, feel free: https://paypal.me/fredo1664

If it has to be in crypto, here's a Monero address:  86ZnDRhUUyufE8uyY8nmXcBJaYLs2Qf6xEVf6ayUfmvQZT57wFYrRW3J632KdEYYMUcQL3YkXYFRoBxAY3rQx13dUacRNUt
