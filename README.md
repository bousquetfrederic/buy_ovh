Python script that uses the OVH API and their Python helper. See here: https://github.com/ovh/python-ovh
You need to create a file ovh.conf with the API keys, including your consumer key.
If you don't know what those are, see here: https://github.com/ovh/python-ovh


You need to edit the script to change in what datacenters you want to search.
You can also specify multiple filters for the name of the server, otherwise the list gets too long.
For example : [KS-LE,KS-A] will look for server names which start with KS-LE or KS-A

Once you have chosen a server that happens to be available, press CTRL-C to stop the infinite loop.
Then you can chose which server you want, and if you want to generate the invoice or pay with your favourite method.

If you end up buying a 600€ server, it's not the script fault, it's yours, because this is just a random python script you found on the internet.
I have only tested with OVH France. I know for some servers overseas it doesn't quite work.
