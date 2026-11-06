"""Independently inspect retained 900-frame synthetic Core/render probe."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    lines = (ROOT/'work/_shared/c102304-core-probe.log').read_text().splitlines()
    scratch = Path(lines[0].removeprefix('scratch '))
    assert scratch.is_relative_to(ROOT/'.runtime-work') and scratch.is_dir()
    summary = json.loads(lines[-1])
    attempt = scratch/'attempt'
    result = json.loads((attempt/'result.json').read_text())
    report = json.loads((attempt/'analysis-report.json').read_text())
    adapter = json.loads((attempt/'converted/adapter_report.json').read_text())
    final = json.loads((attempt/'final-decode.json').read_text())
    assert result['provenance_kind'] == 'synthetic_local_diagnostic'
    assert all(result[key] is False for key in ('setup_confirmed','behavior_attempted',
                                                'maneuver_completed','accepted','legal_verdict_claimed'))
    assert report['original_joins']['frames'] == adapter['frames'] == final['frames'] == 900
    assert adapter['required_measurements_complete'] is True
    for item in adapter['inputs'].values():
        assert sha(item['path']) == item['sha256']
    assert summary['core']['converted'] is True and summary['core']['decoder_checked'] is True
    assert summary['core']['acceptance_claimed'] is False
    assert summary['render']['frames'] == 900 and summary['final_decode_frames'] == 900
    assert final['passed'] is True
    assert final['video_sha256'] == sha(attempt/'event_review.webm')
    assert final['mapping_sha256'] == sha(attempt/'event_review_frames.jsonl')
    template = ROOT/'runtime/pipeline/fixtures/retained-speed/capture/native/graphs/base/00021714.pkl'
    assert template.is_file()
    assert len(list((attempt/'capture/native/graphs/base').glob('*.pkl'))) == 900
    print(json.dumps({'audit':'pass','frames':900,'decoder_checked':True,
                      'final_decode_passed':True,'graph_source':'retained-speed template',
                      'accepted_recordings':0},sort_keys=True))


if __name__ == '__main__':
    main()
