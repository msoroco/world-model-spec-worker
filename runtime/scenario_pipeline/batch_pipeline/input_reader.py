"""Per-worker STDIO read-only tool for one already supplied JSON request.

No shell, database, arbitrary paths, network, or writes. Dies with its caller.
"""
import hashlib,json,sys
from pathlib import Path


def read_input(source, arguments):
    pointer=arguments.get('pointer','');offset=arguments.get('offset',0);limit=arguments.get('limit',20000)
    if not isinstance(pointer,str)or (pointer and not pointer.startswith('/')):raise ValueError('Use an exact JSON pointer')
    if type(offset)is not int or offset<0 or type(limit)is not int or not 1<=limit<=40000:raise ValueError('Invalid bounded offset/limit')
    value=source
    for part in pointer.split('/')[1:]:
        part=part.replace('~1','/').replace('~0','~')
        value=value[int(part)]if isinstance(value,list)else value[part]
    text=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    return {'pointer':pointer,'total_characters':len(text),'offset':offset,'text':text[offset:offset+limit],
            'next_offset':offset+limit if offset+limit<len(text)else None,
            'sha256':hashlib.sha256(text.encode()).hexdigest()}


def main():
    # The coordinator supplies this one immutable path; tools accept no paths.
    source=json.loads(Path(sys.argv[1]).read_text())
    tool={'name':'read_input','description':'Read an exact JSON pointer from the complete supplied scenario request. Read-only, no arbitrary files or commands. Use bounded chunks to access all referenced observation plans and dependencies.',
          'inputSchema':{'type':'object','properties':{'pointer':{'type':'string'},'offset':{'type':'integer','minimum':0},'limit':{'type':'integer','minimum':1,'maximum':40000}},'required':['pointer'],'additionalProperties':False},
          'annotations':{'readOnlyHint':True,'destructiveHint':False,'openWorldHint':False}}
    for line in sys.stdin:
        request=json.loads(line)
        if 'id'not in request:continue
        try:
            method=request['method'];params=request.get('params',{})
            if method=='initialize':result={'protocolVersion':params['protocolVersion'],'capabilities':{'tools':{}},'serverInfo':{'name':'supplied-scenario-input','version':'1'}}
            elif method=='ping':result={}
            elif method=='tools/list':result={'tools':[tool]}
            elif method=='tools/call':
                if params['name']!='read_input':raise ValueError('Only read_input is available')
                result={'content':[{'type':'text','text':json.dumps(read_input(source,params.get('arguments',{})),ensure_ascii=False)}]}
            else:raise ValueError('Unsupported read-only protocol method')
            response={'jsonrpc':'2.0','id':request['id'],'result':result}
        except (KeyError,ValueError,TypeError,IndexError)as exc:
            response={'jsonrpc':'2.0','id':request['id'],'error':{'code':-32602,'message':str(exc)}}
        print(json.dumps(response,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
