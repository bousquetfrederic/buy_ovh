import sys
import yaml
from pathlib import Path

__all__ = ['configFile', 'config_path']

# config path optionally given as argv
config_path = sys.argv[1] if len(sys.argv) > 1 else 'conf.yaml'

configFile = {}
try:
    configFile = yaml.safe_load(Path(config_path).read_text())
except Exception as e:
    # Runs at import time, before logging is configured — print to stderr
    # so the user sees the reason for the exit.
    print("Error with config file")
    print(e)
    sys.exit("Bye now.")
