import sys
import yaml

__all__ = ['configFile']

configFile = {}
try:
    configFile = yaml.safe_load(open('conf.yaml', 'r'))
except Exception as e:
    print("Error with config.yaml")
    print(e)
    sys.exit("Bye now.")

