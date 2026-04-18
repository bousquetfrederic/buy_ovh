import sys
import yaml
from pathlib import Path

__all__ = ['configFile', 'config_path']


def _find_conf_path(argv):
    """Look for --conf PATH / -c PATH / --conf=PATH anywhere in argv.
    Defaults to 'conf.yaml'. Silently ignores unknown args — subcommand
    parsing is the caller's job."""
    it = iter(argv)
    for a in it:
        if a in ('--conf', '-c'):
            nxt = next(it, None)
            if nxt is not None:
                return nxt
        elif a.startswith('--conf='):
            return a.split('=', 1)[1]
    return 'conf.yaml'


config_path = _find_conf_path(sys.argv[1:])

# If the user is only asking for --help, don't block on a missing config —
# argparse will exit right after import. Every other path still needs the
# YAML, so fall back to the old sys.exit in that case.
_wants_help = any(a in ('-h', '--help') for a in sys.argv[1:])

configFile = {}
try:
    configFile = yaml.safe_load(Path(config_path).read_text())
except Exception as e:
    if _wants_help:
        configFile = {}
    else:
        # Runs at import time, before logging is configured — print to
        # stderr so the user sees the reason for the exit.
        print("Error with config file")
        print(e)
        sys.exit("Bye now.")
