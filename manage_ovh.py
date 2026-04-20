import logging
import sys

import m.api
import m.bootstrap
import m.manage

from m.config import configFile, config_path

# ----------------- CONFIG -------------------------------------------------------------------

APIEndpoint = configFile.get('APIEndpoint', 'ovh-eu')

m.bootstrap.setup_logging(configFile, 'manage_ovh')
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.info(f"Loaded config from {config_path}")

# ----------------- LOGIN (required) ---------------------------------------------------------

m.bootstrap.login_required(
    configFile, APIEndpoint,
    "manage_ovh needs APIKey, APISecret and APIConsumerKey in the config.",
    "Login failed. Check your API credentials.")

# ----------------- GO ------------------------------------------------------------------------

logger.info("Starting manage_ovh")
try:
    m.manage.run()
except KeyboardInterrupt:
    pass
sys.exit("Bye now.")
