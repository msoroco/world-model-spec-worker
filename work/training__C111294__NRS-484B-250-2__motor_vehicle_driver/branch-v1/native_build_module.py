"""Constants and source helpers for an exact branch Native request."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
FRAMES=600
RATE=20
CASES=('device_controlled','opposing_no_turn','opposing_left_turn')
POLICIES={'primary':(5.0,'standard',False),
          'fallback1':(4.5,'standard',False),
          'fallback2':(5.0,'elevated_overview',False)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path,obj):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
