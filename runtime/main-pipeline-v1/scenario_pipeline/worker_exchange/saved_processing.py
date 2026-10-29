"""Saved-only processing and compact failure feedback; never starts CARLA."""
import subprocess
import sys
from pathlib import Path
from .common import read,write,sha,within,tree,digest
from .runtime_cli import execution_env,process,render
from .media import audit


def run(manifest,case,attempt,output,library,validator):
    manifest,attempt,output=Path(manifest).resolve(),Path(attempt).resolve(),Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    try:
        entry=next(e for e in read(manifest)['cases'] if e['case_id']==case)
        construction=read(within(manifest.parent,entry['construction']))
        if sha(within(manifest.parent,entry['construction']))!=entry['construction_sha256']:
            raise ValueError('Selected construction changed')
        if read(attempt/'construction.json')!=construction:raise ValueError('Attempt construction differs')
        protected = {str(p.relative_to(attempt)): sha(p) for p in attempt.rglob('*') if p.is_file() and (p.suffix in ('.mkv','.webm','.pkl') or p.name in ('trace.jsonl','video_frames.jsonl','road.xodr') or 'capture' in p.relative_to(attempt).parts)}
        analysis=within(attempt,entry['measurement_procedure']['entrypoint'])
        if not (attempt/'result.json').exists():
            with (output/'analysis.log').open('x') as log:
                subprocess.run([sys.executable,str(analysis),'--attempt',str(attempt),'--output',str(attempt/'analysis-report.json')],
                    cwd=attempt,env=execution_env(),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
        if any(sha(attempt/p)!=checksum for p,checksum in protected.items()):raise ValueError('Saved processing rewrote original acquisition')
        from .native_output import validate_result
        from batch_pipeline.carla import validate_attempt
        result=validate_result(read(attempt/'result.json'))
        if result.get('case_id')!=case:raise ValueError('Wrong case result')
        rows=[line for line in (attempt/result['trace_reference']).read_text().splitlines() if line.strip()]
        mapping=sha(attempt/result['video_frame_map_reference'])
        audits={v:audit(within(attempt,v),len(rows),mapping_sha256=mapping,receipt=output/('source-'+str(i)+'.json')) for i,v in enumerate(result['video_references'])}
        config=read(attempt/'config.json');proposal=next(c for c in read(manifest.parent/'proposals/cases.json')['cases'] if c['case_id']==case)
        validate_attempt(attempt,{'case':proposal,'cell':{'cell_id':config['cell_id']},'actor':config['actor']},construction,{'recorded_exit_code':0},{},source_audits=audits)
        process(attempt,output/'converted',library,validator)
        video=render(attempt,output/'converted',proposal)
        audit(video['video'],len(rows),receipt=output/'final-decode.json')
        receipt={'format':'worker-saved-processing-v1','case_id':case,'passed':True,'recorded_only':True,
                 'physical_acceptance_claimed':False,'remaining':['independent source pixels and physical completion review','unresolved legal judgments']}
        write(output/'processing.json',receipt);return receipt
    except Exception as error:
        write(output/'feedback.json',{'case_id':case,'recorded_only':True,'error_type':type(error).__name__,'error':str(error),
             'manifest_sha256':sha(manifest),'native_replay_requested':False})
        raise
