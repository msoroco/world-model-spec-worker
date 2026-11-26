"""Synthetic source-shape check for the selected recorded-only finalizer."""
import json
import tempfile
from pathlib import Path

from finalize_separator import finalize
from prove_saved import fixture


def main():
    here=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary)
        for suffix,cross,obstruction in (('controlled_1',False,False),('controlled_2',True,False),
            ('emergency_1',True,False),('emergency_2',True,True)):
            attempt=root/suffix
            fixture(attempt,cross,reviewed=False,obstruction=obstruction)
            construction=json.loads((here/'bundles'/suffix/'construction.json').read_text())
            cfg=next(json.loads(item['content']) for item in construction['files']
                if item['path']=='config.json')
            (attempt/'config.json').write_text(json.dumps(cfg)+'\n')
            (attempt/'trace.jsonl').write_text(''.join(json.dumps({
                'frame':i+100,'time_s':i/20,'position_m':[0,0,0],'speed_mps':0})+'\n'
                for i in range(600)))
            report=finalize(attempt,attempt/'analysis-report.json')
            result=json.loads((attempt/'result.json').read_text())
            assert len(report['measurements'])==4
            assert result['target_checks'][0]['matched'] is True
            assert result['setup_confirmed'] is False
            assert result['legal_verdict_claimed'] is False
            assert report['measurements']['separator_geometry']['value']['official_context_review_pending'] is True
            assert report['measurements']['emergency_context']['value']['obstruction_present'] is obstruction
        print(json.dumps({'synthetic_finalizer_passed':True,
            'exact_cases':['controlled_1','controlled_2','emergency_1','emergency_2'],
            'source_context_review_pending':True,
            'physical_acceptance_claimed':False}))


if __name__=='__main__':main()
