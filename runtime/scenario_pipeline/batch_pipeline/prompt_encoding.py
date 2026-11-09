"""Lossless references to supplied inputs when inline model requests exceed limits."""
from copy import deepcopy
import hashlib
import json


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)


def referenced_request(request, path):
    """Retain all law structures inline; reference duplicated/large evidence plans.

    The complete original request remains an explicitly readable, immutable file.
    References use exact JSON pointers, never inferred aliases or law filtering.
    """
    def reference(value, pointer):
        result={'$input_file':str(path),'json_pointer':pointer,'sha256':hashlib.sha256(canonical(value).encode()).hexdigest()}
        if isinstance(value,dict):
            result['identity']={k:value[k]for k in ('template_id','law_id','actor','phrase','note','cell_id','status')if k in value}
            result['object_keys']=list(value)[:32]
            result['object_key_count']=len(value)
        elif isinstance(value,list):
            result['array_length']=len(value)
        return result
    def visit(value,pointer):
        if isinstance(value,dict):
            return {k:reference(v,pointer+'/'+k)if k=='observable_requirements'and isinstance(v,dict)
                    else visit(v,pointer+'/'+k.replace('~','~0').replace('/','~1'))for k,v in value.items()}
        if isinstance(value,list):return [visit(v,pointer+'/'+str(i))for i,v in enumerate(value)]
        return value
    result=visit(request,'')
    for key in ('dependencies','fewshots'):
        value=request.get('inputs',{}).get(key)
        if value is not None:result['inputs'][key]=reference(value,'/inputs/'+key)
    repair=request.get('inputs',{}).get('request',{}).get('repair_context')
    if isinstance(repair,dict):
        for key in ('retained_result','retained_logs','evidence_files'):
            if key in repair:
                result['inputs']['request']['repair_context'][key]=reference(repair[key],'/inputs/request/repair_context/'+key)
    # Keep the exact case inline. If other large context still exceeds the wire
    # budget, expose whole supplied subtrees by hash and exact pointer.
    for key in ('comparison_anchor','construction_group','bindings','simulator_context','templates','law_records','law_summaries','previous_attempt_result',
                'verified_structures','summaries','vocabulary','definitions','capability_sources','actor_reviews','actor_review','historical_proposals'):
        if len(canonical(result))<=220000:
            break
        if key in request.get('inputs',{}):
            result['inputs'][key]=reference(request['inputs'][key],'/inputs/'+key)
    result['transport']={'format':'referenced-inputs-v1','complete_request':str(path),
        'sha256':hashlib.sha256(canonical(request).encode()).hexdigest(),
        'instructions':'Each $input_file/json_pointer is the exact supplied value in the complete request JSON. All templates, applicability decisions, exceptions, observation plans and fewshots are retained. Read referenced values as needed in bounded chunks; consider every supplied law. References are not missing observations or permission to skip requirements.'}
    return result


def resolve_request(encoded, original):
    def expand(value):
        if isinstance(value,dict)and '$input_file'in value and 'json_pointer'in value:
            target=original
            for part in value['json_pointer'].split('/')[1:]:
                part=part.replace('~1','/').replace('~0','~')
                target=target[int(part)]if isinstance(target,list)else target[part]
            if hashlib.sha256(canonical(target).encode()).hexdigest()!=value['sha256']:raise ValueError('Referenced input changed')
            return deepcopy(target)
        if isinstance(value,dict):return {k:expand(v)for k,v in value.items()}
        if isinstance(value,list):return [expand(v)for v in value]
        return value
    return expand({k:v for k,v in encoded.items()if k!='transport'})
