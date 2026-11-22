"""Build exact draft Native constructions for the nine semantic sweep points."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from build_reference_draft import MODULES
from native_channels import channels_for
from sweep_case import SWEEPS, resolve

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def build():
    canonical_path = HERE/'proposals/canonical-cases.json'
    canonical = json.loads(canonical_path.read_text())
    base_paths = {
        'reference': HERE/'construction.json',
        'safe_operation_stop': HERE/'draft-safe_operation_stop-construction.json',
        'law_required_stop': HERE/'draft-law_required_stop-construction.json',
    }
    entries = []
    for semantic in canonical['cases']:
        sweep_id = semantic.get('sweep_id')
        if sweep_id not in SWEEPS:
            continue
        cid = semantic['case_id'] if semantic['case_id'].startswith(HERE.name+'__') else HERE.name+'__'+semantic['case_id']
        base, axis, points = SWEEPS[sweep_id]
        point = semantic['sweep_point']
        if set(point) != {axis} or point[axis] not in points:
            raise ValueError('Semantic case differs from reviewed sweep grid')
        construction = deepcopy(json.loads(base_paths[base].read_text()))
        files = {item['path']:item['content'] for item in construction['files']}
        config = json.loads(files['config.json'])
        config.update(case_id=cid, selected_case_id=cid,
                      case_suffix=base, case={'case_id': cid},
                      sweep={'sweep_id': sweep_id, 'sweep_point': point},
                      recording_description=deepcopy(semantic['recording_description']))
        measurements = semantic.get('sweep_measurements', [])
        if (len(measurements) != 1 or measurements[0].get('variable') != axis or
                measurements[0].get('observable') != axis):
            raise ValueError('Semantic sweep measurement does not bind exact axis')
        config['sweep_measurement'] = deepcopy(measurements[0])
        config['supported_case_ids'] = list(dict.fromkeys(
            config['supported_case_ids'] + [cid]))
        if [item['name'] for item in config['recording_description']['channels']] != list(
                channels_for(base, axis)):
            raise ValueError('Semantic sweep channels differ from source derivation')
        resolve(config)
        files['config.json'] = json.dumps(config, indent=2, sort_keys=True)+'\n'
        for name in MODULES:
            files[name] = (HERE/name).read_text()
        files['native_finalize.py'] = (HERE/'native_sweep_finalize.py').read_text()
        construction.update(case_id=cid,
                            status='draft_cpu_preparation_incomplete',
                            recording_description=config['recording_description'],
                            files=[({'path':name,'content':content,
                                     'source':str((HERE/'native_sweep_finalize.py').relative_to(ROOT))}
                                   if name == 'native_finalize.py' else
                                   {'path':name,'content':content})
                                   for name,content in files.items()])
        construction['measurement_plan']['per_case_contracts'][0]['case_id'] = cid
        construction['mechanisms'] = list(dict.fromkeys(construction['mechanisms'] + [
            'source-measured '+axis+' controlled sweep at '+str(point[axis])]))
        target = HERE/('sweep-'+cid+'-primary-construction.json')
        write(target, construction)
        entries.append({'case_id':cid, 'construction':target.name,
                        'construction_sha256':sha(target)})
    if len(entries) != 9 or len({row['case_id'] for row in entries}) != 9:
        raise ValueError('Nine distinct exact sweep constructions required')
    manifest = {'format':'worker-execution-manifest', 'assignment_id':HERE.name,
                'runtime_manifest_sha256':sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json'),
                'status':'draft_sweep_primary_cpu_diagnostic',
                'canonical_cases_sha256':sha(canonical_path), 'cases':entries}
    target=HERE/'sweep-primary-manifest.json'
    write(target,manifest)
    return {'manifest':target.name,'manifest_sha256':sha(target),
            'cases':len(entries), 'construction_hashes':{x['case_id']:x['construction_sha256'] for x in entries}}


if __name__=='__main__':
    print(json.dumps(build(),indent=2,sort_keys=True))
