"""Synthetic CPU sources must not be accepted as Native branch measurements."""
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from branch_measurement import measure


def main():
    source=HERE/'native/device/offline/raw-fixtures/probe_1/primary'
    rejected={}
    for kind,condition in [('signal','red'),('officer','proceed')]:
        try:measure(source,kind,condition)
        except ValueError as exc:rejected[kind]=str(exc)
        else:raise AssertionError('Synthetic source accepted: '+kind)
    assert rejected=={'signal':'Complete restored original Native attempt required',
                      'officer':'Complete restored original Native attempt required'}
    print(json.dumps({'synthetic_source_rejections':2,'original_native_claimed':False}))


if __name__=='__main__':main()
