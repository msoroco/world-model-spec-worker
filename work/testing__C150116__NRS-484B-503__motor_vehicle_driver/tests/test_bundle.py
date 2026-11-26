"""Root exact source-deferred bundle preflight."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check

def test_bundle():
    case_id, case = check()
    assert case_id.endswith("__" + case.name)
