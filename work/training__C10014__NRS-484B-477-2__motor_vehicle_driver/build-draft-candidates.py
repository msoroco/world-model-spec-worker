"""Build eight exact unselected CPU bundles for the alley entrance pair."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
NATIVE=HERE/'native'
ASSIGNMENT=HERE.name
NAMES=('primary','fallback1','fallback2','fallback3')
RUNTIME_MANIFEST='391baee19ccece687c5632aa2cc64ba3b958c8b492045b30e4bfc4caa131c235'
SOURCES=('runner.py','geometry.py','controller.py','engineering.py',
         'cameras.py','measure_entrance.py','finalize.py')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def build():
    from importlib.util import module_from_spec,spec_from_file_location
    spec=spec_from_file_location('engineering',NATIVE/'engineering.py')
    # engineering imports geometry by module name; importing from native is
    # scoped to this builder and does not affect materialized bundles.
    import sys
    sys.path.insert(0,str(NATIVE))
    engineering=module_from_spec(spec);spec.loader.exec_module(engineering)
    plan=json.loads((HERE/'case-plan.json').read_text())
    template=json.loads((NATIVE/'config.json').read_text())
    shared={name:(NATIVE/name).read_text() for name in SOURCES}
    test=(HERE/'tests/test_native_draft.py').read_text().replace("parents[1]/'native'","parents[1]")
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
              'assignment_id':ASSIGNMENT,'runtime_manifest_sha256':RUNTIME_MANIFEST,
              'status':'draft_not_selected','cases':[]}
    for draft in plan['cases']:
        suffix=draft['case_id'].rsplit('__',1)[-1]
        contract=f'draft-measurements/{suffix}/measurement-contract.json'
        entry={'case_id':draft['case_id'],'kind':'draft_not_selected',
               'candidate_risk':{'status':'physical','reason':
                   'Native abutting-property access, precise stop, route tracking and source-camera framing require original evidence'},
               'measurement_contract':contract,
               'measurement_procedure':{'entrypoint':'finalize.py',
                                        'output_schema':'c10014-alley-entrance-saved-analysis-v1'},
               'candidates':[]}
        for candidate in NAMES:
            config=dict(template)
            config.update(case_id=draft['case_id'],case_suffix=suffix,
                          candidate_id=candidate,selected_case_id=draft['case_id'],
                          supported_case_ids=[draft['case_id']],
                          case={'case_id':draft['case_id']})
            config['cameras']=[{'name':c['name'],'width':c['width'],'height':c['height'],
                                'pose_strategy':'candidate-specific declared Native mount; see cameras.py',
                                'fov_deg':'90/105 according to measured framing fallback'}
                               for c in template['cameras']]
            files=[{'path':name,'content':content} for name,content in shared.items()]
            files.append({'path':'tests/test_native_draft.py','content':test})
            files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
            construction={'case_id':draft['case_id'],'cell_id':'C10014',
                'law_id':'NRS-484B-477-2','actor':'motor_vehicle_driver',
                'entrypoint':'runner.py','files':files,
                'measurement_plan':{'method':'original Native stationary body overlap with authored entrance corridor; see measure_entrance.py',
                                    'status':'prototype_not_runtime_compatible'},
                'recording_description':config['recording_description'],
                'static_checks':['authored alley and access map','controlled stop route and prospective body containment',
                                 'candidate route/braking/camera distinctness','CPU original-source measurement tests'],
                'termination_rules':['full 480 original frames','retain failure on capture or restoration error'],
                'mechanisms':['authored alley plus abutting driveway','observed-pose stop controller',
                              'four synchronized lossless camera sources'],
                'status':'unselected_cpu_draft'}
            relative=f'draft-candidates/{suffix}/{candidate}/construction.json'
            path=HERE/relative;write(path,construction)
            ref={'id':candidate,'construction':relative,'construction_sha256':sha(path)}
            if candidate=='primary':entry.update(ref)
            else:
                trigger=engineering.TRIGGERS[candidate]
                ref.update(trigger={k:trigger[k] for k in ('source','metric','failure_condition')},
                           changed_knobs=trigger['changed_knobs'])
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(HERE/'draft-execution-manifest.json',manifest)
    return {'cases':len(manifest['cases']),'candidates':sum(1+len(c['candidates']) for c in manifest['cases']),
            'status':manifest['status']}


if __name__=='__main__':print(json.dumps(build(),indent=2))
