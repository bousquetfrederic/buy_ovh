import logging
import sys

import m.api
import m.manage

from m.config import configFile, config_path

# ----------------- CONFIG -------------------------------------------------------------------

MAIN_DEFAULTS = {
    'APIEndpoint': 'ovh-eu',
}

LOGGING_DEFAULTS = {
    'logFile': '',
    'logLevel': 'WARNING',
}

def loadConfigMain(cf):
    for name, spec in MAIN_DEFAULTS.items():
        if isinstance(spec, tuple):
            default, yaml_key = spec
        else:
            default, yaml_key = spec, name
        globals()[name] = cf.get(yaml_key, globals().get(name, default))

def loadConfigLogging(cf):
    for name, spec in LOGGING_DEFAULTS.items():
        if isinstance(spec, tuple):
            default, yaml_key = spec
        else:
            default, yaml_key = spec, name
        globals()[name] = cf.get(yaml_key, globals().get(name, default))

loadConfigMain(configFile)

loadConfigLogging(configFile)
if logFile:
    logging.basicConfig(level=logging.getLevelNamesMapping()[logLevel.upper()],
                        format="%(asctime)s [manage_ovh] [%(levelname)s] %(name)s: %(message)s",
                        handlers=[logging.FileHandler(logFile, encoding="utf-8")])
if logLevel == "ERROR":
    logging.getLogger("urllib3").setLevel(logging.ERROR)
else:
    logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.info(f"Loaded config from {config_path}")

# ----------------- LOGIN (required) ---------------------------------------------------------

if not ('APIKey' in configFile and 'APISecret' in configFile
        and 'APIConsumerKey' in configFile):
    sys.exit("manage_ovh needs APIKey, APISecret and APIConsumerKey in the config.")

if not m.api.login(APIEndpoint,
                   configFile['APIKey'],
                   configFile['APISecret'],
                   configFile['APIConsumerKey']):
    sys.exit("Login failed. Check your API credentials.")

# ----------------- GO ------------------------------------------------------------------------

logger.info("Starting manage_ovh")
try:
    m.manage.run()
except KeyboardInterrupt:
    pass
sys.exit("Bye now.")
