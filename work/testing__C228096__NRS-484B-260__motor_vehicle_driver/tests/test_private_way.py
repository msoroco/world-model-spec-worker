"""Run focused original-source and Native acquisition CPU checks."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_private_way_site import PrivateWaySiteTest


__all__ = ["PrivateWaySiteTest"]
