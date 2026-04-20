"""Shared startup helpers for the buy_ovh / monitor_ovh / manage_ovh /
buy_vps entry points. Handles logging and login so each script only
carries the glue that actually differs between them."""
import logging
import sys

import m.api

__all__ = ['setup_logging', 'login_if_credentials', 'login_required']


def setup_logging(conf, prog, stream_fallback=False):
    """Configure root logging from conf['logFile'] / conf['logLevel'].

    When logFile is empty: logs go to stdout if stream_fallback is True
    (monitor_ovh's behavior) and are dropped otherwise. urllib3 is tuned
    to ERROR/WARNING so its noise matches the rest of the logs."""
    log_file = conf.get('logFile', '')
    log_level = conf.get('logLevel', 'WARNING')
    level = logging.getLevelNamesMapping()[log_level.upper()]
    fmt = f"%(asctime)s [{prog}] [%(levelname)s] %(name)s: %(message)s"
    if log_file:
        handlers = [logging.FileHandler(log_file, encoding='utf-8')]
    elif stream_fallback:
        handlers = [logging.StreamHandler(sys.stdout)]
    else:
        handlers = []

    if handlers:
        logging.basicConfig(level=level, format=fmt, handlers=handlers)

    urllib3_level = logging.ERROR if log_level == 'ERROR' else logging.WARNING
    logging.getLogger('urllib3').setLevel(urllib3_level)


def login_if_credentials(conf, endpoint):
    """Login when credentials are present. If APIKey / APISecret are set
    but APIConsumerKey is missing, walk the interactive consumer-key
    issuance flow so the user can paste the new key into conf.yaml.

    Returns True on successful login, False otherwise (including the
    consumer-key path — no active client after that flow)."""
    if not ('APIKey' in conf and 'APISecret' in conf):
        return False
    if 'APIConsumerKey' in conf:
        return m.api.login(endpoint,
                           conf['APIKey'],
                           conf['APISecret'],
                           conf['APIConsumerKey'])
    ck = m.api.get_consumer_key(endpoint, conf['APIKey'], conf['APISecret'])
    if ck != "nokey":
        print("To add the generated consumer key to your conf.yaml file:")
        print("APIConsumerKey: " + ck)
    else:
        print("Failed to get a consumer key, did you authenticate?")
    input("Press Enter to continue...")
    return False


def login_required(conf, endpoint, missing_msg, failed_msg):
    """Login with all three creds; sys.exit on failure. Used by
    manage_ovh and by monitor_ovh when auto_buy is configured."""
    if not ('APIKey' in conf
            and 'APISecret' in conf
            and 'APIConsumerKey' in conf):
        sys.exit(missing_msg)
    if not m.api.login(endpoint,
                       conf['APIKey'],
                       conf['APISecret'],
                       conf['APIConsumerKey']):
        sys.exit(failed_msg)
