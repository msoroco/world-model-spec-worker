"""Mechanical index of existing case validation requirements; no new semantics."""
from .validation import numeric_thresholds


def requirement_index(inputs):
    binding=next((d for d in inputs.get('dependencies',[])if 'variable_parameters'in d),None)
    if binding is None:return None
    active={r['template_id']for r in binding['law_refs']}
    laws=[]
    for template in inputs.get('templates',[]):
        if template['template_id']not in active:continue
        judgments=template['structure']['judgment_calls_needed']
        thresholds=numeric_thresholds(template)
        needs={}
        for judgment in judgments:
            requirement=judgment.get('observable_requirements',{})
            for kind in ('recording_needs','context_inputs'):
                for item in requirement.get(kind,[]):
                    needs[(kind,item['name'],item['unit'])]={'kind':kind,'name':item['name'],'unit':item['unit']}
        laws.append({'law_id':template['law_id'],'template_id':template['template_id'],
            'numeric_triples':[{'threshold_ref':path,**threshold}for path,threshold in thresholds],
            'plain_attempt_pair_required':not judgments and not thresholds,
            'judgment_refs':[{'phrase':j['phrase'],'note':j.get('note','')}for j in judgments],
            'required_recording_names':list(needs.values())})
    return {'assignment_names_and_kinds':{v['name']:v.get('kind',v.get('type'))for v in binding['variable_parameters']},
        'laws':laws,'source':'Mechanical index of pinned templates, bindings and the existing validator',
        'instructions':'Keep exactly these assignment names, including baseline defaults. Preserve every listed threshold_ref and linked below/at/above triple, every required plain pair, and every judgment plan. Use exact required recording names/units in each target-law description. This index is supplemental: full source methods and requirements remain authoritative. Shared recording defaults contain only evidence genuinely common to every member. Give each target-law case and sweep a complete target-specific recording_description covering every required target-law observation/context, physical cause, held setup fact and original motion/graph/video evidence. Do not inherit unrelated unsupported channels from other target laws into every case merely because they share cell bindings. Every other law retains its own full case/sweep requirements and coverage, and all bound variables remain assigned. If a required channel for that target cannot be realized, mark that plan incomplete with the precise missing input. This instruction applies to new planning proposals; never remove a channel, alter an assignment, or change a meaning in an already frozen case to make construction pass.'}
