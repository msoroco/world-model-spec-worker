"""Independent exact full-resolution v1 package receipt/artifact audit."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    lines=(HERE/'package-v1-full-primary-probe.log').read_text().splitlines()
    assert len(lines)==2 and lines[0].startswith('scratch ')
    scratch=Path(lines[0].split(' ',1)[1]).resolve()
    assert scratch.is_relative_to((REPO/'.runtime-work').resolve())
    result=json.loads(lines[1])
    assert result['case_id'].endswith('__at_100_ft') and result['candidate_id']=='primary'
    assert result['synthetic'] and not result['selected'] and not result['original_pixels']
    assert result['negative']['exit_code']!=0 and result['negative']['removed']=='native_samples.jsonl'
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    entry=next(e for e in manifest['cases'] if e['case_id']==result['case_id'])
    assert sha(HERE/entry['construction'])==entry['construction_sha256']==result['positive']['construction_sha256']
    output=scratch/'output'
    receipt=json.loads((output/'compatibility.json').read_text())
    assert receipt['format']=='worker-package-compatibility-v1' and receipt['passed']
    assert receipt['construction_sha256']==entry['construction_sha256']
    assert receipt['analysis_sha256']==sha(output/'finalize.py')
    assert receipt['log_sha256']==sha(output/'compatibility-analysis.log')
    assert {'actual_analysis','native_validation','mandatory_observations','lean_decoder',
            'render','final_decode','acquisition_unchanged'}<=set(receipt['checks'])
    report=json.loads((output/'analysis-report.json').read_text())
    native=json.loads((output/'result.json').read_text())
    assert report['original_joins']['frames']==800
    assert native['provenance_kind']=='synthetic_cpu_fixture' and not native['accepted']
    assert all(frames==800 for frames in report['video_frames'].values())
    core=json.loads((output/'converted/adapter_report.json').read_text())
    assert core['frames']==800 and core['required_measurements_complete']
    assert core['decoder_validation']['passed']
    final=json.loads((output/'final-decode.json').read_text())
    assert final['passed'] and final['frames']==800
    negative=(scratch/'negative-analysis.log').read_text()
    assert 'Missing required source: native_samples.jsonl' in negative
    print(json.dumps({'exact_full_resolution_v1_positive':True,'removed_source_negative':True,
                      'core_lean_render_final_decode':True,'frames':800,'selected':False,
                      'original_pixels':False}))


if __name__=='__main__':main()
