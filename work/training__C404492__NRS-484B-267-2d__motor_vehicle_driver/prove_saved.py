"""Four-camera source-hash diagnostic for 600-frame emergency cases."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from measure_emergency import CAMERAS,measure,sha
from prove_emergency import fixture


def main():
    with tempfile.TemporaryDirectory(prefix='emergency-saved-',dir=os.environ['TMPDIR']) as tmp:
        root=Path(tmp)/'source';fixture(root,True)
        ctx_path=root/'emergency_context.json';ctx=json.loads(ctx_path.read_text())
        ctx['review_kind']='original_source_review'
        poses=[dict(json.loads(s),source_kind='original_native_pose') for s in (root/'vehicle_poses.jsonl').read_text().splitlines()]
        (root/'vehicle_poses.jsonl').write_text(''.join(json.dumps(p)+'\n' for p in poses))
        hashes={}
        for name in CAMERAS:
            path=root/(name+'.mkv')
            run=subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
                'color=c=black:s=16x16:r=20','-frames:v','600','-c:v','ffv1',str(path)],capture_output=True,text=True)
            if run.returncode:raise AssertionError('Diagnostic source camera failed: '+run.stderr[-300:])
            hashes[path.name]=sha(path)
        ctx['camera_sha256']=hashes;ctx_path.write_text(json.dumps(ctx)+'\n')
        out=measure(root)
        assert out['samples']==600 and len(out['source_sha256'])==8
        ctx['camera_sha256']['side.mkv']='0'*64;ctx_path.write_text(json.dumps(ctx)+'\n')
        try:measure(root)
        except ValueError:pass
        else:raise AssertionError('Changed camera source accepted')
        print(json.dumps({'joined_frames':600,'decoded_cameras':4,'changed_camera_hash_rejected':True,
            'legal_result':None},sort_keys=True))


if __name__=='__main__':main()
