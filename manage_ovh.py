import logging
import sys

import m.api
import m.manage

from m.config import configFile

# ----------------- CONFIG -------------------------------------------------------------------

def loadConfigMain(cf):
    global APIEndpoint
    APIEndpoint = cf['APIEndpoint'] if 'APIEndpoint' in cf else APIEndpoint

def loadConfigLogging(cf):
    global logFile, logLevel
    logFile = cf['logFile'] if 'logFile' in cf else logFile
    logLevel = cf['logLevel'] if 'logLevel' in cf else logLevel

APIEndpoint = "ovh-eu"
loadConfigMain(configFile)

logFile = ""
logLevel = "WARNING"
loadConfigLogging(configFile)
if logFile:
    logging.basicConfig(level=logging.getLevelNamesMapping()[logLevel.upper()],
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                        handlers=[logging.FileHandler(logFile, encoding="utf-8")])
if logLevel == "ERROR":
    logging.getLogger("urllib3").setLevel(logging.ERROR)
else:
    logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

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
