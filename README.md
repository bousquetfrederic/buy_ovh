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
The interactive one. It fetches the catalog at startup and drops you in a navigator — everything happens from there, there is no separate command prompt.

- `↑`/`↓` (or `j`/`k`) move the cursor; `PgUp`/`PgDn`, `g`/`G` for jumps.
- `!` buys the highlighted row, `?` requests an invoice for it. To create several orders at once, type a number first (vim style): `3!` places three identical orders.
- `/` opens filter mode. The focus jumps to the filter row under the column headers; `←`/`→` (or `Tab`) moves between columns, typing edits the regex, `Enter` applies, `Esc` cancels, `Ctrl-U` clears the current cell. Numeric columns (price, fee, total) accept `<N`, `>N`, `<=N`, `>=N`, `=N`, or a bare number (treated as `<=N`). `X` clears every filter at once. The `filterName` / `filterDisk` / `filterMemory` / `maxPrice` keys in `conf.yaml` are a separate layer applied at catalog-fetch time and do not show up in the filter bar.
- `M` cycles the commitment term 1 → 12 → 24 months, `T` toggles VAT, `r` refreshes the catalog, `R` reloads `conf.yaml` from disk.
- `c`/`f`/`b`/`u`/`U`/`$` toggle CPU / FQN / BW columns, include-unavailable, include-unknown-availability and fake-buy mode.
- `h` opens the in-app key reference, `q` or `Esc` quits.

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
