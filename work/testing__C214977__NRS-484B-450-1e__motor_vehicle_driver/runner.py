"""Exact C214977 crosswalk case entrypoint; local Native adapter remains required."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load_config():
    c = json.loads((ROOT/'config.json').read_text())
    assert (c['law_id'], c['cell_id'], c['actor']) == ('NRS-484B-450-1e','C214977','motor_vehicle_driver')
    assert c['selected_case_id'] == c['case']['case_id']
    assert c['rate_hz'] == 20 and c['duration_s'] == 45
    assert [v['name'] for v in c['cameras']] == ['overview','approach','reference_corner','driver_reference']
    assert c['case']['action'] in ('stop','stand','park')
    assert c['case']['destination'] in ('on','off')
    return c

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port')
    a = parser.parse_args()
    c = load_config()
    if a.check:
        print(json.dumps({'case_id':c['selected_case_id'],'identity_checked':True,'capture_profile_checked':True,'simulation_started':False}))
        return
    raise RuntimeError('Native CARLA adapter and saved capture integration are not implemented; do not execute this draft bundle')

if __name__ == '__main__': main()
