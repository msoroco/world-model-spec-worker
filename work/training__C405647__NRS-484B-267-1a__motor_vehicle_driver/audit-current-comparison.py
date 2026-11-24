"""Independently compare all three exact paired synthetic request branches."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def source(suffix,name):
    r=json.loads((HERE/f'current-{suffix}-recipe.json').read_text())
    return ROOT/next(x['source'] for x in r['sources'] if x['path']==name)
def rows(p): return [json.loads(x) for x in p.read_text().splitlines()]
def main():
    m=json.loads((HERE/'execution-manifest.json').read_text())
    entries={x['case_id'].rsplit('__',1)[-1]:x for x in m['cases']}
    results=[]
    for branch,a,b in [('witness','witness_1','witness_2'),('exception','exception_1_1','exception_1_2'),('official','official_1','official_2')]:
        pair=[]
        for suffix in (a,b):
            entry=entries[suffix];path=source(suffix,'actor-frames.jsonl');samples=rows(path)
            receipt=HERE/'current-public'/(suffix+'-primary-compatibility.json')
            processing=HERE/'current-public'/(suffix+'-primary-processing.json')
            c=json.loads(receipt.read_text());s=json.loads(processing.read_text())
            if not(c['passed'] and s['passed'] and s['recorded_only'] and c['construction_sha256']==entry['construction_sha256']):
                raise ValueError('Selected source or proof changed: '+suffix)
            if len(samples)!=480: raise ValueError('Incomplete 480-frame comparison: '+suffix)
            pair.append(samples)
        left,right=pair
        for i,(x,y) in enumerate(zip(left,right)):
            if x['frame']!=y['frame'] or x['time_s']!=y['time_s'] or x['approach']!=y['approach']:
                raise ValueError('Fixed approach or frame context changed: '+branch+'/'+str(i))
            if branch=='exception' and x['subject']!=y['subject']:
                raise ValueError('Officer exception changed subject request')
            if branch!='exception' and x.get('front_red_flash_on')!=y.get('front_red_flash_on'):
                raise ValueError('Paired lamp request changed')
        if branch=='exception':
            if any(x['direction_requested'] for x in left) or not any(x['direction_requested'] for x in right):
                raise ValueError('Officer direction request did not separate exception pair')
            variable='officer_direction_request'
            values=[sum(x['direction_requested'] for x in samples) for samples in pair]
        else:
            values=[samples[-1]['subject']['y_m'] for samples in pair]
            if not values[0]<values[1]-2: raise ValueError('Yield request did not separate pair')
            variable='requested_lateral_yield_response'
        result={'branch':branch,'case_ids':[entries[s]['case_id'] for s in (a,b)],'frames_per_case':480,
          'fixed_approach_and_frame_join':True,'comparison_variable':variable,'values':values,
          'sources':{s:{'actor_frames_sha256':sha(source(s,'actor-frames.jsonl')),
            'compatibility_sha256':sha(HERE/'current-public'/(s+'-primary-compatibility.json')),
            'processing_sha256':sha(HERE/'current-public'/(s+'-primary-processing.json'))} for s in (a,b)},
          'diagnostic_only':True,'original_native_observed':False,'physical_acceptance':False,'legal_verdict':None}
        results.append(result)
    path=HERE/'current-public/comparison-audit.json'
    path.write_text(json.dumps({'format':'c405647-1a-current-comparison-audit','comparisons':results},indent=2)+'\n')
    print(json.dumps({'passed':True,'branches':len(results),'comparison_sha256':sha(path)}))
if __name__=='__main__':main()
