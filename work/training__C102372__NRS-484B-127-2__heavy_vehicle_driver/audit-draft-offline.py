"""Independent exact C102372 source, candidate and pinned offline receipt audit."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline'))
from scenario_pipeline.worker_exchange.candidate_constructions import validate


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    summary=json.loads((HERE/'draft-offline-summary.json').read_text())
    records={(row['case_id'],row['candidate_id']):row for row in summary['results']}
    if len(records)!=28 or len(manifest['cases'])!=7:raise ValueError('Twenty-eight exact receipts required')
    checked=[]
    for entry in manifest['cases']:
        validate(HERE,entry,'NRS-484B-127-2','C102372',candidate_count=4)
        suffix=entry['case_id'].rsplit('__',1)[-1]
        hashes=set();base=None
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            ref=entry if candidate=='primary' else next(
                row for row in entry['candidates'] if row['id']==candidate)
            path=HERE/ref['construction']
            if sha(path)!=ref['construction_sha256'] or ref['construction_sha256'] in hashes:
                raise ValueError('Construction hash or distinctness differs')
            hashes.add(ref['construction_sha256'])
            construction=json.loads(path.read_text())
            if (construction['case_id'],construction['law_id'],construction['cell_id'],
                construction['actor'])!=(entry['case_id'],'NRS-484B-127-2','C102372',
                                          'heavy_vehicle_driver'):
                raise ValueError('Frozen C102372 construction identity differs')
            files={item['path']:item['content'] for item in construction['files']}
            for name in ('runner.py','engineering.py','geometry.py','measure_gap.py',
                         'trigger_measure.py','finalize.py','two_lane_engineering.py',
                         'two_lane_exception.py','passing_carveout.py',
                         'passing_engineering.py','passing_trigger.py',
                         'passing_hold_engineering.py','passing_hold_trigger.py',
                         'conditions_qualifier.py','conditions_engineering.py',
                         'conditions_trigger.py'):
                if files[name]!=(HERE/'native'/name).read_text():
                    raise ValueError('Bundled Native source differs: '+name)
            if files['tests/test_native.py']!=(HERE/'native/test_native.py').read_text():
                raise ValueError('Bundled CPU tests differ')
            if files['tests/test_two_lane_native.py']!=(HERE/'native/test_two_lane_native.py').read_text():
                raise ValueError('Bundled two-lane CPU tests differ')
            if files['tests/test_passing_native.py']!=(HERE/'native/test_passing_native.py').read_text():
                raise ValueError('Bundled passing CPU tests differ')
            if files['tests/test_passing_hold_native.py']!=(HERE/'native/test_passing_hold_native.py').read_text():
                raise ValueError('Bundled hold CPU tests differ')
            if files['tests/test_conditions_native.py']!=(HERE/'native/test_conditions_native.py').read_text():
                raise ValueError('Bundled conditions CPU tests differ')
            config=json.loads(files['config.json'])
            if config['candidate_id']!=candidate or config['case_suffix']!=suffix:
                raise ValueError('Exact config differs')
            if base is None:base=config
            elif {k:config[k] for k in ('law_id','cell_id','actor','rate_hz','duration_s',
                                       'required_atoms','recording_description')}!={
                                       k:base[k] for k in ('law_id','cell_id','actor','rate_hz',
                                       'duration_s','required_atoms','recording_description')}:
                raise ValueError('Fallback changed law-preserving config')
            receipt=records[entry['case_id'],candidate]
            if receipt['exit_code'] or receipt['construction_sha256']!=ref['construction_sha256'] or \
                    sha(HERE/receipt['command_log'])!=receipt['command_log_sha256'] or \
                    sha(HERE/receipt['unit_log'])!=receipt['unit_log_sha256'] or \
                    'Ran 16 tests' not in (HERE/receipt['unit_log']).read_text():
                raise ValueError('Pinned exact offline receipt differs')
            checked.append({'case':suffix,'candidate':candidate,
                            'construction_sha256':ref['construction_sha256']})
    return {'passed':True,'exact_unselected_bundles':checked,
            'physical_or_selected_claim':False}


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
