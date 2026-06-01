import os
import sys

# Ensure tests can import app package when running pytest directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
