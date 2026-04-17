import os
import sys

# Tests import from the project root (buy_ovh.py, monitor_ovh.py, m/*).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
