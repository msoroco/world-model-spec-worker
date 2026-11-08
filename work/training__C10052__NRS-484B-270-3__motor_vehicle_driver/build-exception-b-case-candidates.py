"""Materialize eight exact, unselected traffic-conflict Native bundles."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
AID=HERE.name
NAMES=('primary','fallback1','fallback2','fallback3')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')

def main():
    parent=json.loads((HERE/'draft-rider-execution-manifest.json').read_text())
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
        'assignment_id':AID,'runtime_manifest_sha256':parent['runtime_manifest_sha256'],
        'status':'draft_not_selected','cases':[]}
    for response in ('faulted','healthy'):
        suffix='exception_b_'+response;case_id=AID+'__'+suffix
        entry={'case_id':case_id,'kind':'draft_not_selected',
            'candidate_risk':{'status':'physical','reason':'Native applied fault, physical propulsion response, camera pixels and lane occupancy require original readback'},
            'measurement_contract':'exception-b-measurement-contract.json',
            'measurement_procedure':{'entrypoint':'finalize_exception_b.py',
                'output_schema':'c10052-saved-exception-b-diagnostic-v1'},'candidates':[]}
        for name in NAMES:
            base=json.loads((HERE/'draft-rider-cases'/'rider_bicycle_clear'/name/'construction.json').read_text())
            base['case_id']=case_id;base['status']='unselected_cpu_draft'
            base['measurement_plan']={'method':'saved original Native applied fault, propulsion response and ego body diagnostic',
                'status':'exact_bundle_unselected_original_native_pending'}
            base['static_checks']=['exact exception B case identity','480 synchronized Native frames',
                'four original camera views','original powertrain and ego body samples']
            description=base['recording_description']
            description['channels']=[c for c in description['channels'] if c['name'] not in ('ru.bicycle','ru.pedestrian')]
            files=[]
            for item in base['files']:
                path=item['path'];content=item['content']
                if path=='runner.py':content=(HERE/'native/exception_b_runner.py').read_text()
                elif path=='config.json':
                    config=json.loads(content)
                    config.update(case_id=case_id,case_suffix=suffix,candidate_id=name,
                        selected_case_id=case_id,supported_case_ids=[case_id],case={'case_id':case_id},
                        rider_type='disabled_vehicle',rider_response=response)
                    config['required_atoms']=sorted(set(config['required_atoms'])-{'ru.bicycle','ru.pedestrian'})
                    config['mandatory_channels']=sorted(set(config['mandatory_channels'])-{'ru.bicycle','ru.pedestrian'})
                    config['recording_description']=description
                    content=json.dumps(config,indent=2)+'\n'
                elif path=='tests/test_bundle.py':
                    content=("import json\nimport unittest\nfrom pathlib import Path\nimport runner\n\n"
                        "class ExactExceptionBCase(unittest.TestCase):\n"
                        "    def test_check(self):\n"
                        "        result=runner.check(json.loads(Path('config.json').read_text()))\n"
                        "        self.assertEqual(result['camera_count'],4)\n"
                        "        self.assertFalse(result['native_imported'])\n")
                if path not in ('finalize_rider.py',):files.append({'path':path,'content':content})
            for module in ('exception_b_engineering','exception_b_geometry','exception_b_native','finalize_exception_b'):
                files.append({'path':module+'.py','content':(HERE/'native'/(module+'.py')).read_text()})
            base['files']=files;base['recording_description']=description
            output=HERE/'draft-exception-b-exact-cases'/suffix/name/'construction.json'
            write(output,base)
            row={'id':name,'construction':output.relative_to(HERE).as_posix(),
                'construction_sha256':sha(output)}
            if name=='primary':entry.update(row)
            else:
                metric={'fallback1':'fault_observation_frames','fallback2':'propulsion_test_frames',
                    'fallback3':'scripted_reference_visible_fraction'}[name]
                row.update(trigger={'source':'source-hashed exception B CPU fixture; original Native trigger pending',
                    'metric':metric},changed_knobs={'fallback1':['observation end 240 to 300 frames'],
                    'fallback2':['propulsion test 60 to 90 frames'],
                    'fallback3':['reference camera relocated']}[name])
                entry['candidates'].append(row)
        manifest['cases'].append(entry)
    path=HERE/'draft-exception-b-execution-manifest.json';write(path,manifest)
    print(json.dumps({'cases':2,'candidates':8,'manifest_sha256':sha(path),'selected':False}))

if __name__=='__main__':main()
