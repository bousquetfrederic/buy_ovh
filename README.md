# buy_ovh.py
Python script that uses the OVH API and their Python helper. See here: https://github.com/ovh/python-ovh

It could make sense to grab the latest release (see the sidebar) instead of cloning the repository (or if you do, to checkout the latest release) if you would like something potentially a tiny bit less unstable.

The 'ovh' and 'PyYAML' modules must be installed.
```
pip install ovh
```
```
pip install PyYAML
```

The main program is buy_ovh.py. There is also a small program availability_monitor which just does the availability monitoring.

There is a conf file that you need to make, conf.yaml, where you can define stuff. There is an example file provided. The file explains all the parameters.

In there you at least need the following for the connection to the API: endpoint, api key and secret, and a consumer key. You can read about them at the python-ovh repo (above).
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

If it has to be in crypto, here's a Monero address:  8BTX8pJYmtf6STY2s7TdTT3NATocMpMReeV6DP5Vgnfx8MWBMXoTMypDjWv4Wf639habTNTED9bXSV9pYXs8s7BCHERFUxh
