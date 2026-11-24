"""Add active-runtime diagnostic finalization to branch case constructions."""
import json
from pathlib import Path
from branch_requests import HERE

BASE=HERE/'cases/branch-requests'


def write(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')


def upgrade():
    finalizer=(HERE/'branch-diagnostic-finalize.py').read_text();count=0
    for suffix in ('signal_red_stop','signal_green_proceed','officer_no_direction_stop','officer_directed_proceed'):
        for candidate in ('primary','fallback1'):
            bundle=BASE/(suffix if candidate=='primary' else suffix+'-'+candidate)
            cfg=json.loads((bundle/'config.json').read_text())
            cfg.update(selected_case_id=cfg['case_id'],required_atoms=['kin.speed'],source_packets=[],
                       cameras=['overview','approach','reference_corner','driver_reference'],
                       case={'case_id':cfg['case_id'],'recording_description':cfg['recording_description']})
            write(bundle/'config.json',cfg);(bundle/'finalize.py').write_text(finalizer)
            construction=json.loads((bundle/'construction.json').read_text())
            files={f['path']:f for f in construction['files']}
            files['config.json']['content']=(bundle/'config.json').read_text()
            files['finalize.py']={'path':'finalize.py','content':finalizer}
            construction['files']=list(files.values())
            construction['recording_description']=cfg['recording_description']
            write(bundle/'construction.json',construction)
            count+=1
    return count


if __name__=='__main__':print(upgrade())
