"""Recompute recorded streams; never promotes missing observations or legal verdicts."""
import argparse,json,pathlib,math

def summarize(rows,window,statistic):
 values=[r['value'] for r in rows if window[0]<=r['time_s']<=window[1] and isinstance(r['value'],(float,int)) and not isinstance(r['value'],bool)]
 if not values:raise ValueError('No measured scalar samples in frozen window')
 if statistic=='mean':return sum(values)/len(values)
 if statistic=='min':return min(values)
 if statistic=='max':return max(values)
 if statistic=='first':return values[0]
 if statistic=='last':return values[-1]
 raise ValueError('Unsupported statistic')
def main():
 p=argparse.ArgumentParser();p.add_argument('output_dir');p.add_argument('--channel',required=True);p.add_argument('--start',type=float,required=True);p.add_argument('--end',type=float,required=True);p.add_argument('--statistic',choices=['mean','min','max','first','last'],required=True);a=p.parse_args();root=pathlib.Path(a.output_dir)
 rows=[json.loads(s) for s in (root/('channel-'+a.channel.replace('.','_')+'.jsonl')).read_text().splitlines()];value=summarize(rows,[a.start,a.end],a.statistic)
 out={'name':a.channel,'value':value,'sample_window_s':[a.start,a.end],'statistic':a.statistic,'source':'channel-'+a.channel.replace('.','_')+'.jsonl','legal_verdict':None,'status':'diagnostic_pending_full_capture_validation'}
 with (root/('summary-'+a.channel.replace('.','_')+'.json')).open('x') as f:json.dump(out,f,indent=2)
if __name__=='__main__':main()
