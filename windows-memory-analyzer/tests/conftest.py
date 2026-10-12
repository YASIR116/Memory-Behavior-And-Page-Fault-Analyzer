"""
tests/conftest.py
─────────────────────────────────────────────────────────────────────────────
Pytest configuration.  Adds the project root to sys.path so that
`from analysis.metrics import ...` style imports work from the tests/ dir.
"""

import sys
import os

# Insert the project root (parent of tests/) at the front of sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
