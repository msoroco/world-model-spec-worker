"""Return deterministic CPU motion/lifecycle fixtures for each entry alternative."""
import hashlib
import json
from pathlib import Path

from space_physical_audit import assess, LIFECYCLE, validate_lifecycle


ROOT=Path(__file__).resolve().parent
OUT=ROOT/'physical'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    Path(path).write_text(json.dumps(value,indent=2)+'\n')


def main():
    OUT.mkdir(exist_ok=True)
    results={}
    for region in ('crosswalk','intersection'):
        spec=json.loads((ROOT/f'diagnostic-{region}_clear_downstream.json').read_text())
        scene=OUT/f'{region}-scene.json'
        frames=OUT/f'{region}-frames.jsonl'
        incomplete=OUT/f'{region}-incomplete-frames.jsonl'
        scene.write_text(spec['files']['space_scene.json'])
        frames.write_text(spec['files']['space_frames.jsonl'])
        incomplete.write_text(''.join(frames.read_text().splitlines(keepends=True)[:4]))
        for kind,source in [('complete_motion',frames),('incomplete_motion',incomplete),
                            ('missing_evidence',OUT/f'{region}-missing-frames.jsonl')]:
            result=assess(scene,source,'native')
            expected={'complete_motion':'met','incomplete_motion':'not_met',
                      'missing_evidence':'unverified'}[kind]
            if result['physical_checks']['maneuver']['status']!=expected:
                raise ValueError(region+' '+kind+' did not produce '+expected)
            result['fixture_kind']='simulated_native_cpu_packet'
            result['region_kind']=region
            result_path=OUT/f'{region}-{kind}.json'
            write(result_path,result)
            results[(region,kind)]=result_path
    validate_lifecycle(LIFECYCLE)
    try:
        validate_lifecycle(LIFECYCLE[:-2]+tuple(reversed(LIFECYCLE[-2:])))
    except ValueError:
        pass
    else:
        raise AssertionError('early saved processing was not rejected')
    print('CPU physical outcomes and early-processing rejection passed')


if __name__=='__main__':
    main()
