"""Four-camera saved-source hash diagnostic for two-phase approach."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from native.measure_approach import CAMERAS,measure,sha
from prove_approach import fixture


def main():
    with tempfile.TemporaryDirectory(prefix='c405647-2f-saved-',dir=os.environ['TMPDIR']) as tmp:
        root=Path(tmp)/'source';fixture(root,True)
        ctx_path=root/'emergency_context.json';ctx=json.loads(ctx_path.read_text())
        ctx['review_kind']='original_source_review'
        poses=[dict(json.loads(x),source_kind='original_native_pose') for x in (root/'vehicle_poses.jsonl').read_text().splitlines()]
        (root/'vehicle_poses.jsonl').write_text(''.join(json.dumps(p)+'\n' for p in poses))
        hashes={}
        for name in CAMERAS:
            p=root/(name+'.mkv')
            q=subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
                              'color=c=black:s=16x16:r=20','-frames:v','600','-c:v','ffv1',str(p)],capture_output=True,text=True)
            if q.returncode:raise AssertionError('Diagnostic camera failed: '+q.stderr[-300:])
            hashes[p.name]=sha(p)
        ctx['camera_sha256']=hashes;ctx_path.write_text(json.dumps(ctx)+'\n')
        report=measure(root)
        assert report['samples']==600 and len(report['source_sha256'])==7
        ctx['camera_sha256']['driver_reference.mkv']='0'*64;ctx_path.write_text(json.dumps(ctx)+'\n')
        try:measure(root)
        except ValueError as e:
            if 'Camera source hash differs' not in str(e):raise
        else:raise AssertionError('Changed camera source accepted')
        print(json.dumps({'joined_frames':600,'decoded_cameras':4,'changed_camera_hash_rejected':True,
                          'native_executed':False,'legal_result':None},sort_keys=True))
if __name__=='__main__':main()
