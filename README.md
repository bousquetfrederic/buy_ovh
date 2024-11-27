Python script that uses the OVH API and their Python helper. See here: https://github.com/ovh/python-ovh

You need to create a file ovh.conf with the API keys, including your consumer key.
If you don't know what those are, see here: https://github.com/ovh/python-ovh

There is a conf file that you can make, conf.yaml, where you can define stuff.
There is an example file provided.
To know what does what, read the code.
If that file does not exist, default values are used.

The colour coding is in the code. Red is unavailable. Green and yellow are available. Etc.

Once you have chosen a server that happens to be available, press CTRL-C to stop the infinite loop.
Then you can chose which server you want, and if you want to generate the invoice or pay with your favourite method.

You can also toggle the display of some stuff.

If you end up buying a 600€ server, it's not the script fault, it's yours, because this is just a random python script you found on the internet.
I have only tested with OVH France.
