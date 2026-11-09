"""Reject fields the authoritative decoder would silently ignore."""
from collections import Counter
from functools import lru_cache
import re


@lru_cache(maxsize=8)
def fields(library):
    from .adapter import full_core
    text=(full_core(library)/'Runtime/Decode.lean').read_text()
    result={}
    for name in ('kin','signals','roadUser','laneInfo',"structure'",'device','scene','env','posture','conditions'):
        match=re.search(r'^def '+re.escape(name)+r'\s.*?(?=^def |\Z)',text,re.M|re.S)
        if match is None:raise ValueError('Decoder function missing: '+name)
        keys=set(re.findall(r'(?:req|opt|optList|list) j path "([^"]+)"',match[0]))
        keys.update(re.findall(r'field\? j "([^"]+)"',match[0]))
        if not keys:raise ValueError('No decoder fields found: '+name)
        result[name]=keys
    return result


def objects(scene):
    yield 'scene',scene
    if isinstance(scene.get('env'),dict):yield 'env',scene['env']
    for user in scene.get('users',[]):
        yield 'roadUser',user
        for key,name in [('kin','kin'),('sig','signals'),('posture','posture')]:
            if isinstance(user.get(key),dict):yield name,user[key]
    for region in scene.get('structures',[]):
        yield "structure'",region
        if isinstance(region.get('lane'),dict):yield 'laneInfo',region['lane']
    for device in scene.get('devices',[]):
        yield 'device',device
        if isinstance(device.get('conditions'),dict):yield 'conditions',device['conditions']


def ignored(scene,library,*,remove=False):
    allowed=fields(str(library));counts=Counter()
    for name,value in objects(scene):
        for key in set(value)-allowed[name]:
            counts[name+'.'+key]+=1
            if remove:del value[key]
    return counts


def validate(scene,library):
    unknown=ignored(scene,library)
    if unknown:raise ValueError('Fields ignored by current Core decoder: '+', '.join(sorted(unknown)))
