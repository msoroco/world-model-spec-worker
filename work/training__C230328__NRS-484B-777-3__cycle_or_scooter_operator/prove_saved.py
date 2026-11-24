"""Exercise four-camera original-source join using local diagnostic media."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from measure_abreast import measure,sha,CAMERAS
from prove_abreast import fixture


def main():
    with tempfile.TemporaryDirectory(prefix='abreast-saved-',dir=os.environ['TMPDIR']) as tmp:
        root=Path(tmp)/'source';fixture(root,2)
        ctx_path=root/'road_context.json';ctx=json.loads(ctx_path.read_text())
        ctx['review_kind']='original_source_review'
        rows=[dict(json.loads(s),source_kind='original_native_pose') for s in (root/'rider_poses.jsonl').read_text().splitlines()]
        (root/'rider_poses.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        hashes={}
        for name in CAMERAS:
            path=root/(name+'.mkv')
            run=subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
                'color=c=black:s=16x16:r=20','-frames:v','600','-c:v','ffv1',str(path)],
                capture_output=True,text=True)
            if run.returncode:raise AssertionError('Diagnostic camera encode failed: '+run.stderr[-300:])
            hashes[path.name]=sha(path)
        ctx['camera_sha256']=hashes;ctx_path.write_text(json.dumps(ctx)+'\n')
        result=measure(root)
        assert result['sample_count']==600 and len(result['source_sha256'])==7
        ctx['camera_sha256']['side.mkv']='0'*64;ctx_path.write_text(json.dumps(ctx)+'\n')
        try:measure(root)
        except ValueError:pass
        else:raise AssertionError('Tampered camera binding accepted')
        print(json.dumps({'joined_frames':600,'camera_sources':4,'camera_hash_tamper_rejected':True,
            'abreast_classification':None,'legal_result':None},sort_keys=True))


if __name__=='__main__':main()
