"""Independent saved-artifact audit of the 800-frame Core/Lean/render probe."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    lines=(HERE/'core-synthetic-probe.log').read_text().splitlines()
    assert len(lines)==2 and lines[0].startswith('scratch ')
    scratch=Path(lines[0].split(' ',1)[1]).resolve()
    assert scratch.is_relative_to((REPO/'.runtime-work').resolve())
    attempt=scratch/'attempt'
    claimed=json.loads(lines[1]); report=json.loads((attempt/'analysis-report.json').read_text())
    result=json.loads((attempt/'result.json').read_text())
    core=json.loads((attempt/'converted/adapter_report.json').read_text())
    decoder=core['decoder_validation']
    decode=json.loads((attempt/'final-decode.json').read_text())
    assert report['original_joins']['frames']==800 and all(x==800 for x in report['video_frames'].values())
    assert result['provenance_kind']=='synthetic_cpu_fixture' and not result['accepted']
    assert not result['setup_confirmed'] and not result['behavior_attempted'] and not result['maneuver_completed']
    assert core['frames']==800 and core['required_measurements_complete'] is True
    assert decoder['passed'] and 'decoded_frames=800' in decoder['output'] and 'full_core=true' in decoder['output']
    assert decode['passed'] and decode['frames']==800
    assert claimed['render_frames']==800 and claimed['final_decode_passed'] and claimed['synthetic'] and not claimed['accepted']
    inputs=core['inputs']
    for item in inputs.values():
        if isinstance(item,dict) and 'path' in item and 'sha256' in item:
            path=Path(item['path']);assert path.is_relative_to(attempt) and sha(path)==item['sha256']
    capture=json.loads((attempt/'capture/manifest.json').read_text())
    assert capture['synthetic_diagnostic'] and capture['frames']==800
    assert len((attempt/'capture/native/frames.jsonl').read_text().splitlines())==800
    print(json.dumps({'frames':800,'core_required_complete':True,'lean_decoder_passed':True,
                      'render_final_decode_passed':True,'original_native_observed':False}))


if __name__=='__main__':main()
