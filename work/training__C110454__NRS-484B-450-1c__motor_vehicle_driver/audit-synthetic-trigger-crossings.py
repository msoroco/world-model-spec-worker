"""Independently compare synthetic parking trigger sources with their base cases."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from importlib.machinery import SourceFileLoader
proof_module=SourceFileLoader('trigger_proof',str(HERE/'prove-synthetic-trigger-crossings.py')).load_module()
CASES=('probe_a','probe_b')
VARIANTS=('baseline','fallback1','fallback2','fallback3')


def read_rows(path):return [json.loads(line) for line in path.read_text().splitlines()]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    proof=json.loads((HERE/'synthetic-trigger-crossings.json').read_text())
    if (proof['passed'] is not True or proof['source_kind']!='synthetic_cpu_fixture' or
        proof['original_native_or_pixels_observed'] is not False or proof['selected'] is not False or
        len(proof['rows'])!=8):raise AssertionError('Synthetic trigger proof differs')
    seen=set()
    for item in proof['rows']:
        case,variant=item['case'],item['variant']
        if case not in CASES or variant not in VARIANTS or (case,variant) in seen:
            raise AssertionError('Source case inventory differs')
        seen.add((case,variant))
        native=HERE/'fixtures/trigger-crossings'/f'{case}-{variant}-native.jsonl'
        pixel=HERE/'fixtures/trigger-crossings'/f'{case}-{variant}-pixels.jsonl'
        if sha(native)!=item['native_sha256'] or sha(pixel)!=item['pixel_sha256']:
            raise AssertionError('Source hash differs')
        base=read_rows(HERE/'fixtures'/case/'native_samples.jsonl')
        rows=read_rows(native);marks=read_rows(pixel)
        if len(rows)!=480 or len(marks)!=40:raise AssertionError('Frame inventory differs')
        for i,(actual,original) in enumerate(zip(rows,base)):
            expected=json.loads(json.dumps(original))
            if variant=='fallback1' and i==30:
                for point in expected['body_xy_m']:point[1]+=0.6
            if variant=='fallback2' and i>=440:expected['speed_m_s']=0.3
            if actual!=expected:raise AssertionError('Native crossing changed another field')
        for i,mark in enumerate(marks):
            if mark!={'video_frame':i,'source_kind':'synthetic_pixel_margin_mark',
                      'body_margin_px':39 if variant=='fallback3' and i==0 else 50}:
                raise AssertionError('Pixel crossing changed another field')
        metrics,decisions=proof_module.measure(native,pixel,item['native_sha256'],item['pixel_sha256'])
        if metrics!=item['metrics'] or decisions!=item['decisions'] or decisions!={
            name:name==variant for name in VARIANTS[1:]}:
            raise AssertionError('Derived trigger differs')
    if seen!={(case,variant) for case in CASES for variant in VARIANTS}:
        raise AssertionError('Missing crossing')
    print(json.dumps({'passed':True,'cases':2,'source_hashed_crossings':8,
                      'distinct_trigger_crossings_per_case':3,'selected':False,
                      'original_native_or_pixels_observed':False},sort_keys=True))


if __name__=='__main__':main()
