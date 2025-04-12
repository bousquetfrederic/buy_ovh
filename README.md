# buy_ovh
Python script that uses the OVH API and their Python helper. See here: https://github.com/ovh/python-ovh

The 'ovh' and 'PyYAML' modules must be installed.
```
pip install ovh
```
```
pip install PyYAML
```

There is a conf file that you need to make, conf.yaml, where you can define stuff. There is an example file provided.
In there you at least need the following for the connection to the API: endpoint, api key and secret, and a consumer key. The script will guide you if you don't know what they are. You can also read about them at the python-ovh repo (above).
To know what parameter does what, read the code.
It's recommended to have at least a filter on the server name (or plan code) otherwise the list will be huge.

The colour coding is in the code. Red is unavailable. Green and yellow are available. Etc.

Once you have chosen a server that happens to be available, press CTRL-C to stop the infinite loop.
Then you can chose which server you want, and if you want to generate the invoice or pay with your favourite method.

You can also toggle the display of some stuff, and change or empty the filters.

If you end up buying a 600€ server, it's not the script fault, it's yours, because this is just a random python script you found on the internet.
I have only tested with OVH France.
