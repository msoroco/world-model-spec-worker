"""Root exact source-gated bundle preflight."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check

def test_bundle():
    case_id, device, facility, condition = check()
    assert case_id.endswith("__" + device + "__" + facility + "__" + condition + "_path")
