"""Build exact two-case, four-candidate offline constructions from current sources."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
NATIVE = ROOT/'native'
OUT = ROOT/'selected-all'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n')


def build():
    template = json.loads((ROOT/'selected-primary/reference/construction.json').read_text())
    proposal = json.loads((ROOT/'proposals/cases.json').read_text())
    cases = {item['case_id']: item for item in proposal['cases']
             if item['target_type'] != 'baseline'}
    runtime = REPO/json.loads((REPO/'batch.json').read_text())['runtime']['root']/'SOURCE-MANIFEST.json'
    entries = []
    for witness in ('reference', 'contrast'):
        case_id = ROOT.name+'__'+witness
        selected = cases[case_id]
        alternatives = []
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            source = ROOT/'offline/bundles'/witness/candidate
            cfg = json.loads((source/'config.json').read_text())
            cfg.update(selected_case_id=case_id, duration_s=12,
                required_atoms=[], source_packets=[], case=selected,
                supported_case_ids=[case_id], physical_success_claimed=False,
                cameras=json.loads(next(item['content'] for item in template['files']
                    if item['path']=='config.json'))['cameras'])
            files = []
            for item in template['files']:
                name = item['path']
                if name == 'config.json':
                    content = json.dumps(cfg, indent=2)+'\n'
                elif name in ('requested-tracks.jsonl', 'assignment-source.json',
                              'case-plan.json') or name.startswith('saved/'):
                    content = (source/name).read_text()
                elif name == 'capture.py':
                    content = (NATIVE/name).read_text()
                else:
                    content = item['content']
                files.append({'path': name, 'content': content})
            construction = dict(template, case_id=case_id, files=files,
                                recording_description=selected['recording_description'])
            path = OUT/witness/candidate/'construction.json'
            write(path, construction)
            if candidate != 'primary':
                trigger = {
                    'fallback1': {'source': 'saved source-camera visibility rows',
                        'metric': 'first_40_visible_frames', 'failure_condition': '< 20 frames'},
                    'fallback2': {'source': 'saved reviewed stand position rows',
                        'metric': 'maximum_reviewed_trajectory_deviation_m',
                        'failure_condition': '> 0.2 m'},
                    'fallback3': {'source': 'saved Native actor speed rows',
                        'metric': 'first_40_stopped_frames', 'failure_condition': '< 10 frames'}}[candidate]
                alternatives.append({'id': candidate,
                    'construction': path.relative_to(OUT).as_posix(),
                    'construction_sha256': sha(path), 'trigger': trigger,
                    'changed_knobs': [{'fallback1': 'approach_frames',
                        'fallback2': 'camera_policy',
                        'fallback3': 'motion_policy'}[candidate]]})
            else:
                primary = path
        entries.append({'case_id': case_id, 'kind': 'delivery',
            'construction': primary.relative_to(OUT).as_posix(),
            'construction_sha256': sha(primary),
            'candidate_risk': {'status': 'physical',
                'reason': 'Generated curb stand, actual stopping and source-camera visibility remain unverified'},
            'candidates': alternatives})
    manifest = {'format': 'worker-execution-manifest',
        'assignment_id': ROOT.name, 'status': 'selected_offline_proof_in_progress',
        'runtime_manifest_sha256': sha(runtime),
        'source_branch': 'non_taxicab_parking_in_taxicab_stand',
        'cases': entries, 'original_native_observed': False,
        'delivery_ready': False}
    path = OUT/'draft-manifest.json'
    write(path, manifest)
    return {'cases': len(entries), 'constructions': len(entries)*4,
            'manifest_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(build()))
