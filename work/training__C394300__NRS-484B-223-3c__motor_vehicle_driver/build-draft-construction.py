"""Refresh exact authored map, controlled routes and CPU geometry proof."""
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from geometry import TARGET_FEET,check,open_drive,route  # noqa: E402


def build():
    output=HERE/'draft-construction';output.mkdir(exist_ok=True)
    result=check()
    (output/'scene.xodr').write_text(open_drive())
    for case in TARGET_FEET:
        (output/f'route-{case}.json').write_text(json.dumps(route(case)))
    (output/'geometry-check.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(build()))
