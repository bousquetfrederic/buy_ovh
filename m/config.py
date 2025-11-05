import sys
import yaml

__all__ = ['configFile']

# config path optionally given as argv
config_path = sys.argv[1] if len(sys.argv) > 1 else 'conf.yaml'

configFile = {}
try:
    print(f"Loading config from {config_path}")
    configFile = yaml.safe_load(open(config_path, 'r'))
except Exception as e:
    print("Error with config.yaml")
    print(e)
    sys.exit("Bye now.")
