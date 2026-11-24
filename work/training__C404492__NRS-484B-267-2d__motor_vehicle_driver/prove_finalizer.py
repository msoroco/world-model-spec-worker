"""Exercise saved-only case identity, source joins and fail-closed output."""
import json
import os
from pathlib import Path
import tempfile

from finalize import finalize
from measure_emergency import AID
from prove_emergency import fixture


def reject(source,case,output):
    try:finalize(source,case,output,diagnostic=True)
    except ValueError:return
    raise AssertionError('Invalid saved source accepted')


def main():
    with tempfile.TemporaryDirectory(prefix='emergency-finalizer-',dir=os.environ['TMPDIR']) as tmp:
        root=Path(tmp)
        source=root/'source';fixture(source,False)
        case=AID+'__controlled_1'
        report=root/'report.json'
        result=finalize(source,case,report,diagnostic=True)
        assert result['samples']==600 and report.is_file()
        saved=json.loads(report.read_text())
        assert saved['case_id']==case and saved['selected_outcome_observed'] is None
        reject(source,case,report)
        reject(source,AID+'__controlled_2',root/'wrong-case.json')
        second=root/'second';fixture(second,True)
        second_ctx=second/'emergency_context.json'
        ctx=json.loads(second_ctx.read_text());ctx['case_id']=AID+'__controlled_2'
        second_ctx.write_text(json.dumps(ctx)+'\n')
        second_report=root/'second-report.json'
        assert finalize(second,ctx['case_id'],second_report,diagnostic=True)['samples']==600
        assert json.loads(second_report.read_text())['case_id']==ctx['case_id']
        trace=source/'trace.jsonl';data=trace.read_bytes();trace.unlink()
        reject(source,case,root/'missing-trace.json')
        trace.write_bytes(data)
        try:finalize(source,case,root/'false-original.json')
        except ValueError:pass
        else:raise AssertionError('Synthetic source accepted as original')
        print(json.dumps({'case_ids':[case,ctx['case_id']],'saved_samples_each':600,'positive_passed':True,
            'existing_output_rejected':True,'wrong_case_rejected':True,
            'missing_trace_rejected':True,'false_original_rejected':True,
            'original_native_executed':False},sort_keys=True))


if __name__=='__main__':main()
