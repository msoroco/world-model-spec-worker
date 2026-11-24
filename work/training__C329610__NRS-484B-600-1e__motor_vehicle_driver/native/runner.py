"""CPU-checkable C329610 speed/turn request; Native capture pending."""
import argparse
import json
from pathlib import Path
from speed_turn import check_config,read_and_measure

def main():
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
 p.add_argument('--measure-request');a=p.parse_args()
 root=Path(__file__).resolve().parent
 cfg=json.loads((root/'config.json').read_text())
 out=check_config(cfg,(root/'road.xodr').read_text())
 if a.measure_request:
  out['request_meter']=read_and_measure(a.measure_request,'authored_native_request')
 if not a.check and not a.measure_request:
  raise ValueError('Native capture/source sealing still required')
 print(json.dumps(out,sort_keys=True))

if __name__=='__main__':main()
