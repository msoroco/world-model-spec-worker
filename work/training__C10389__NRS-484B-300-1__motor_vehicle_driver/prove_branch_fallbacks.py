"""CPU proof that branch camera fallback keeps the statutory variable fixed."""
import hashlib
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent;BASE=HERE/'cases/branch-requests';sys.path.insert(0,str(BASE))
from signal_check import check as signal_check
from officer_check import check as officer_check


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    entries=json.loads((BASE/'fallback-bundles.json').read_text());validated=[]
    for entry in entries:
        suffix=entry['case_id'].rsplit('__',1)[1];base=BASE/suffix;fallback=BASE/(suffix+'-fallback1')
        (signal_check if suffix.startswith('signal_') else officer_check)(fallback)
        primary=json.loads((base/'config.json').read_text());alternate=json.loads((fallback/'config.json').read_text())
        for key in ('case_id','requested_signal_aspect' if suffix.startswith('signal_') else 'requested_officer_direction',
                    'road_sha256','tracks_sha256','rate_hz','frames','duration_s'):
            if primary[key]!=alternate[key]:raise ValueError('Fallback changed statutory or source variable: '+key)
        if alternate['camera_policy']!='elevated_overview' or primary['camera_policy']!='standard':
            raise ValueError('Fallback camera contrast absent')
        if sha(base/'requested-tracks.jsonl')!=sha(fallback/'requested-tracks.jsonl'):
            raise ValueError('Fallback altered requested trajectory')
        if sha(fallback/'construction.json')!=entry['construction_sha256']:
            raise ValueError('Fallback construction hash changed')
        validated.append(entry['case_id'])
    if len(validated)!=4:raise ValueError('Incomplete branch fallback set')
    return {'format':'c10389-branch-fallback-proof-v1','validated_case_ids':validated,
            'fixed_condition':'same statutory contrast and source trajectory',
            'changed_knob':'overview camera pose','native_executed':False,'selected_delivery':False}


if __name__=='__main__':
    proof=main();(BASE/'fallback-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'validated_fallbacks':len(proof['validated_case_ids'])}))
