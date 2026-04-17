# buy_ovh
Three little Python scripts wrapped around the OVH API and their Python helper. See here: https://github.com/ovh/python-ovh

Install the dependencies:
```
pip install -r requirements.txt
```

There is a conf file that you need to make, conf.yaml, where you can define stuff. There is an example file provided. The file explains all the parameters. You can keep one conf.yaml for all three scripts or split it — each script ignores the keys it doesn't use.

In there you at least need the following for the connection to the API: endpoint, api key and secret. You can read about them at the python-ovh repo (above). A consumer key is also needed but buy_ovh will help you generate one if you have not got one.

It's recommended to have at least a filter on the server name (or plan code) otherwise the list will be huge.

## buy_ovh
The interactive one. It fetches the catalog at startup and drops you in a navigator where you move with the arrow keys, press Enter on a line to buy it (or get an invoice), `!` to buy now without asking, `?` for an invoice without asking. Press `:` to drop to the command prompt where you can change filters, toggle columns, VAT, the number of months, etc. From the prompt, `I` goes back to interactive and an empty ENTER refreshes.

The colour coding is in the code. Red is unavailable. Green and yellow are available. Etc.

If you end up buying a 600€ server, it's not the script fault, it's yours, because this is just a random python script you found on the internet.

## monitor_ovh
The headless one. Runs forever, refreshing availability and the catalog every `sleepsecs`, and can email you when servers appear or disappear or when their availability changes. It can also auto-buy servers that match an `auto_buy` rule. Credentials are only required if `auto_buy` is set — for plain monitoring, the public endpoints are enough. Run it in tmux or as a systemd service.

## manage_ovh
A small TUI to browse your servers and your orders (unpaid or undelivered). Press Enter on an order to open its URL in your browser.

I have only tested with OVH France.

# Donations
If you would like to make a small donation because this script helped you get the server of your dreams, feel free: https://paypal.me/fredo1664

If it has to be in crypto, here's a Monero address:  86ZnDRhUUyufE8uyY8nmXcBJaYLs2Qf6xEVf6ayUfmvQZT57wFYrRW3J632KdEYYMUcQL3YkXYFRoBxAY3rQx13dUacRNUt
