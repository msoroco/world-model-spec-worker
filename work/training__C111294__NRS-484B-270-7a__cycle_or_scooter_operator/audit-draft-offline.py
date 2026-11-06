"""Independent eight-bundle frozen-identity, source and offline receipt audit."""
import hashlib
import json
from pathlib import Path
import sys

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline'))
from scenario_pipeline.worker_exchange.candidate_constructions import validate

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    manifest=json.loads((FOLDER/'draft-execution-manifest.json').read_text())
    summary=json.loads((FOLDER/'draft-offline-summary.json').read_text())
    records={(row['case_id'],row['candidate_id']):row for row in summary['results']}
    if len(records)!=8 or len(manifest['cases'])!=2:raise ValueError('Eight exact receipts required')
    observed=[]
    for entry in manifest['cases']:
        validate(FOLDER,entry,'NRS-484B-270-7a','C111294',candidate_count=4)
        suffix=entry['case_id'].split('__')[-1]
        hashes=set()
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            ref=entry if candidate=='primary' else next(row for row in entry['candidates'] if row['id']==candidate)
            path=FOLDER/ref['construction'];folder=path.parent
            if sha(path)!=ref['construction_sha256'] or ref['construction_sha256'] in hashes:
                raise ValueError('Construction hash or candidate distinctness differs')
            hashes.add(ref['construction_sha256'])
            construction=json.loads(path.read_text())
            if (construction['case_id'],construction['law_id'],construction['cell_id'],construction['actor'])!=(
                    entry['case_id'],'NRS-484B-270-7a','C111294','cycle_or_scooter_operator'):
                raise ValueError('Frozen construction identity differs')
            files={row['path']:row['content'] for row in construction['files']}
            if files['runner.py']!=(FOLDER/'native/runner.py').read_text() or \
                    files['runner_capture.py']!=(FOLDER/'native/runner_capture.py').read_text() or \
                    files['geometry.py']!=(FOLDER/'native/geometry.py').read_text() or \
                    files['measure.py']!=(FOLDER/'native/measure.py').read_text() or \
                    files['trigger_measure.py']!=(FOLDER/'native/trigger_measure.py').read_text() or \
                    files['finalize.py']!=(FOLDER/'native/finalize.py').read_text():
                raise ValueError('Bundled source differs from owned implementation')
            config=json.loads(files['config.json'])
            if config['candidate_id']!=candidate or config['case_suffix']!=suffix:
                raise ValueError('Bundled exact config differs')
            receipt=records[entry['case_id'],candidate]
            if receipt['exit_code']!=0 or receipt['construction_sha256']!=ref['construction_sha256'] or \
                    sha(FOLDER/receipt['command_log'])!=receipt['command_log_sha256'] or \
                    sha(FOLDER/receipt['unit_log'])!=receipt['unit_log_sha256']:
                raise ValueError('Exact offline receipt differs')
            if 'Ran 5 tests' not in (FOLDER/receipt['unit_log']).read_text():
                raise ValueError('Pinned five-test bundle did not complete')
            observed.append({'case':suffix,'candidate':candidate,'construction_sha256':ref['construction_sha256']})
    print(json.dumps({'passed':True,'exact_unselected_bundles':observed,
                      'selected_or_physical_claim':False},sort_keys=True))

if __name__=='__main__':main()
