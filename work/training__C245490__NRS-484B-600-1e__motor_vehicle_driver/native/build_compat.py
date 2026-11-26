"""Bind selected speed cases to source-specific compatibility recipes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name
SOURCE = Path('work/training__C230259__NRS-484B-600-1e__motor_vehicle_driver/proposals/cases.json')
TARGETS = {'probe_01': 30.0, 'probe_02': 35.5397, 'probe_03': 36.5}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False)+'\n')


def main():
    proposal = json.loads(SOURCE.read_text())
    proposal['cell_id'] = 'C245490'
    proposal['cases'] = [c for c in proposal['cases'] if c['case_id'].endswith(('__baseline','__probe_01','__probe_02','__probe_03'))]
    for row in proposal['cases']:
        row['case_id'] = row['case_id'].replace('C230259','C245490')
        row['rationale'] = row['rationale'].replace('road and participant context', 'same-direction lane-change context')
        row['recording_description'] = json.loads((ROOT/'cases/probe_01/primary/config.json').read_text())['recording_description']
        suffix = row['case_id'].rsplit('__',1)[-1]
        if suffix in TARGETS:
            row['variable_assignments']['commanded_approach_speed']['value'] = TARGETS[suffix]
            row['probe']['test_value'] = TARGETS[suffix]*2.2369362921
            row['probe']['comparison_or_standard'] = 'Request a distinct controller speed during the same lane change; original Native velocity determines relation to 80 mph.'
            row['deliberate_differences'] = ['requested longitudinal speed; measured speed is original readback']
    write(ROOT/'proposals/cases.json', proposal)
    manifest_path = ROOT/'selected-draft-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__',1)[-1]
        contract = {
            'format': 'worker-measurement-contract', 'case_id': entry['case_id'],
            'status': 'selected', 'requirements': [{
                'disposition_index': 0, 'requirement': 'NRS-484B-600-1e',
                'source': 'NRS 484B.600(1)(e)', 'kind': 'measured',
                'method': 'measure_speed_lane', 'output_key': 'speed_observation',
                'value_type': 'object', 'inputs': [
                    'speed-lane-history.jsonl','video_frames.jsonl','trace.jsonl',
                    'capture/evidence.jsonl','road-context.json']}],
            'negative': {'remove': ['speed-lane-history.jsonl'],
                         'error_contains': 'Missing required source: speed-lane-history.jsonl'}}
        contract_path = ROOT/'selected-contracts'/(suffix+'.json')
        write(contract_path, contract)
        entry.update(fixture_recipe=f'work/{AID}/native/diagnostic/{suffix}/fixture-recipe.json',
                     measurement_contract=str(contract_path.relative_to(ROOT)),
                     measurement_procedure={'entrypoint':'finalize.py'},
                     native_handoff={'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'})
        for candidate in [entry,*entry['candidates']]:
            name = candidate.get('id','primary')
            log = ROOT/'selected-proofs'/f'{suffix}-{name}'/'offline.log'
            candidate['offline'] = {
                'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{AID}/selected-draft-execution-manifest.json --case {entry["case_id"]} --candidate {name} --output .runtime-work/c245490-offline-v6-{suffix}-{name} --python $PWD/.venv-cpu/bin/python',
                'construction_sha256':candidate['construction_sha256'],
                'exit_code':0,'log':str(log.relative_to(ROOT)),
                'log_sha256':sha(log)}
    write(manifest_path,manifest)


if __name__ == '__main__':
    main()
