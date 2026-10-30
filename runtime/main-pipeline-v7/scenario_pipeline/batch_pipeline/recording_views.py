"""Explicit physical-unit views of one retained structured recording.

Views select saved fields; they never convert units or merge different quantities.
"""
import math
import re

NUMERIC_UNITS={'s','ms','m','ft','m/s','mph','km/h','rad','deg','rad/s','deg/s','m/s²','m/s^2','1/m','ratio','count','Hz'}


def views(channel):
    result={}
    for view in channel.get('unit_views',[]):
        unit=view.get('unit');fields=view.get('fields')
        if not isinstance(unit,str) or not isinstance(fields,dict) or not fields:
            raise ValueError('Unit view requires exact unit and nonempty field pointers')
        components={part.strip()for part in re.split(r'\s+and\s+|[;,]\s*(?:and\s+)?',unit)}
        if not components<=NUMERIC_UNITS or set(fields.values())!=components:
            raise ValueError('Unit view fields must cover exactly its physical component units')
        if unit in result:raise ValueError('Duplicate unit view')
        if any(not isinstance(path,str)or not path.startswith('/')for path in fields):
            raise ValueError('Unit view fields require absolute JSON pointers into the saved record')
        result[unit]=fields
    if result and channel.get('unit') not in ('structured','structured record'):
        raise ValueError('Physical unit views require a structured recording, never a scalar unit alias')
    return result


def pointer(record,path):
    value=record
    for part in path.split('/')[1:]:
        key=part.replace('~1','/').replace('~0','~')
        value=value[int(key)]if isinstance(value,list)else value[key]
    return value


def numeric(value):
    if isinstance(value,dict):return bool(value)and all(numeric(v)for v in value.values())
    if isinstance(value,list):return bool(value)and all(numeric(v)for v in value)
    return isinstance(value,(int,float))and not isinstance(value,bool)and math.isfinite(value)


def verify(channel,records):
    declared=views(channel)
    if not declared:return
    for record in records:
        for fields in declared.values():
            for path,unit in fields.items():
                try:value=pointer(record,path)
                except (KeyError,IndexError,TypeError,ValueError):
                    raise ValueError('Missing recorded unit-view field: '+channel['name']+' '+path)
                if not numeric(value):raise ValueError('Unobserved/non-numeric unit-view field: '+channel['name']+' '+path)
                if unit=='count' and isinstance(value,(int,float))and value!=int(value):
                    raise ValueError('Recorded count must be integral')


def normalize_result(value):
    """Translate descriptive-only view syntax to the existing representation field.

    Retain authored selectors verbatim. Numeric views and their evidence checks
    are never changed; no quantity, method or requirement is removed.
    """
    import copy
    value=copy.deepcopy(value);changes=[]
    defaults=value.get('case_defaults',{}) if isinstance(value,dict) else {}
    # These two standard planning annotations are per-member metadata, not
    # assignment defaults. Preserve their intended inheritance verbatim.
    for key in ('execution_readiness','missing_inputs'):
        if key in defaults:
            annotation=defaults.pop(key)
            for member in value.get('cases',[])+value.get('sweep_specs',[]):
                member.setdefault(key,copy.deepcopy(annotation))
            changes.append({'field':key,'operation':'inherit standard planning annotation into members'})
    def walk(item):
        if isinstance(item,dict):
            if {'name','unit','method','unit_views'}<=item.keys():
                numeric_views=[];descriptive=[]
                for view in item['unit_views']:
                    unit=view.get('unit','');fields=view.get('fields',{})
                    descriptor=isinstance(unit,str)and any(word in unit for word in ('categor','structured','metadata','native','description','record','text'))
                    physical=isinstance(fields,dict)and any(u in NUMERIC_UNITS for u in fields.values() if isinstance(u,str))
                    if descriptor and not physical:descriptive.append(view)
                    else:numeric_views.append(view)
                if descriptive:
                    item['unit_views']=numeric_views
                    item.setdefault('descriptive_unit_views',[]).extend(descriptive)
                    units=item.setdefault('representation_units',[])
                    for view in descriptive:
                        if view['unit']not in units:units.append(view['unit'])
                    changes.append({'name':item['name'],'descriptive_units':[view['unit']for view in descriptive]})
            for child in item.values():walk(child)
        elif isinstance(item,list):
            for child in item:walk(child)
    walk(value)
    return value,changes


def repair_candidate(inputs,evidence):
    """Recover only same-job candidates whose sole repaired format now validates."""
    import hashlib,json
    from pathlib import Path
    from .sweeps import expand_sweeps
    from .stages import validate
    evidence=Path(evidence)
    match=re.fullmatch(r'attempt-(\d+)',evidence.name)
    if not match:return None
    current=int(match[1]);candidates=[]
    for path in evidence.parent.glob('attempt-*/candidate.json'):
        number=re.fullmatch(r'attempt-(\d+)',path.parent.name)
        if number and int(number[1])<current and path.resolve().parent.parent==evidence.parent.resolve():
            candidates.append((int(number[1]),path))
    binding=next((v for v in inputs.get('dependencies',[])if 'variable_parameters'in v),None)
    if binding is None:return None
    for _,path in sorted(candidates,reverse=True):
        raw=path.read_bytes()
        try:
            result,changes=normalize_result(json.loads(raw))
            if not changes:continue
            expand_sweeps(result,inputs.get('templates',[]),binding)
            validate('cases',result,inputs)
        except (ValueError,KeyError,TypeError):continue
        return result,{'adapter':'mechanical_metadata_view_repair','new_model_call':False,
            'source_candidate':str(path),'source_sha256':hashlib.sha256(raw).hexdigest(),
            'recording_view_normalization':changes,'validation':'All original case-stage checks against current pinned inputs'}
    return None
