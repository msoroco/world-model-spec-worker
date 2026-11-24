"""Read pickle syntax as inert data. No object construction/import/reducer execution."""
from dataclasses import dataclass
import pickletools, math, struct
class FormatError(ValueError): pass
@dataclass(eq=False)
class Opaque:
    kind: str
    args: object = None
    state: object = None
MARK=object()
def decode(data, max_bytes=64*1024*1024, max_ops=2000000, max_memo=500000):
    if not isinstance(data, bytes) or len(data)>max_bytes: raise FormatError('byte limit/type')
    stack=[];memo={};stopped=False
    def pop():
        if not stack: raise FormatError('stack underflow')
        return stack.pop()
    def mark():
        for i in range(len(stack)-1,-1,-1):
            if stack[i] is MARK:
                v=stack[i+1:];del stack[i:];return v
        raise FormatError('missing MARK')
    def pairs(target,values):
        if not isinstance(target,dict) or len(values)%2: raise FormatError('invalid dictionary')
        for i in range(0,len(values),2):
            try:
                if values[i] in target: raise FormatError("duplicate dictionary key")
                target[values[i]]=values[i+1]
            except TypeError: raise FormatError('unhashable dictionary key')
    try:
        for count,(op,arg,pos) in enumerate(pickletools.genops(data),1):
            if count>max_ops or len(stack)>100000 or len(memo)>max_memo: raise FormatError('resource limit')
            n=op.name
            if n in ('PROTO','FRAME'): continue
            if n=='MARK': stack.append(MARK)
            elif n in ('NONE','NEWTRUE','NEWFALSE'): stack.append({'NONE':None,'NEWTRUE':True,'NEWFALSE':False}[n])
            elif n in ('BININT','BININT1','BININT2','INT','LONG','LONG1','LONG4','FLOAT','BINFLOAT','UNICODE','BINUNICODE','SHORT_BINUNICODE','BINUNICODE8','STRING','BINSTRING','SHORT_BINSTRING','BINBYTES','SHORT_BINBYTES','BINBYTES8','BYTEARRAY8'): stack.append(bytes(arg) if isinstance(arg,bytearray) else arg)
            elif n=='EMPTY_DICT':stack.append({})
            elif n=='EMPTY_LIST':stack.append([])
            elif n=='EMPTY_TUPLE':stack.append(())
            elif n=='EMPTY_SET':stack.append(set())
            elif n in ('TUPLE','LIST','DICT','FROZENSET'):
                vs=mark()
                if n=='DICT': x={};pairs(x,vs)
                else:x={'TUPLE':tuple,'LIST':list,'FROZENSET':frozenset}[n](vs)
                stack.append(x)
            elif n in ('TUPLE1','TUPLE2','TUPLE3'):
                k=int(n[-1]);vs=[pop() for _ in range(k)];stack.append(tuple(reversed(vs)))
            elif n in ('SETITEM','SETITEMS'):
                if n=='SETITEM':v=pop();k=pop();vs=[k,v]
                else:vs=mark()
                if not stack:raise FormatError('missing dictionary')
                pairs(stack[-1],vs)
            elif n in ('APPEND','APPENDS','ADDITEMS'):
                vs=[pop()] if n=='APPEND' else mark()
                if not stack:raise FormatError('missing container')
                target=stack[-1]
                if n=='ADDITEMS':
                    if not isinstance(target,set):raise FormatError('set target')
                    target.update(vs)
                else:
                    if not isinstance(target,list):raise FormatError('list target')
                    target.extend(vs)
            elif n in ('BINPUT','LONG_BINPUT','PUT','MEMOIZE'):
                if not stack:raise FormatError('empty memo value')
                key=len(memo) if n=='MEMOIZE' else int(arg)
                if key in memo:raise FormatError('duplicate memo slot')
                memo[key]=stack[-1]
            elif n in ('BINGET','LONG_BINGET','GET'):
                key=int(arg)
                if key not in memo:raise FormatError('unknown memo slot')
                stack.append(memo[key])
            elif n=='GLOBAL':stack.append(Opaque('global',tuple(arg.split(' ',1))))
            elif n=='STACK_GLOBAL':
                name=pop();module=pop()
                if not isinstance(name,str) or not isinstance(module,str):raise FormatError('global names')
                stack.append(Opaque('global',(module,name)))
            elif n in ('REDUCE','NEWOBJ','NEWOBJ_EX'):
                kwargs=pop() if n=='NEWOBJ_EX' else None;args=pop();target=pop()
                if not isinstance(args,tuple):raise FormatError('object arguments')
                stack.append(Opaque(n,(target,args,kwargs)))
            elif n=='BUILD':
                state=pop()
                if not stack or not isinstance(stack[-1],Opaque) or stack[-1].state is not None:raise FormatError('opaque BUILD target')
                stack[-1].state=state
            elif n in ('BINPERSID','PERSID'):stack.append(Opaque('persistent',pop() if n=='BINPERSID' else arg))
            elif n=='POP':pop()
            elif n=='POP_MARK':mark()
            elif n=='DUP':
                if not stack:raise FormatError('empty DUP')
                stack.append(stack[-1])
            elif n=='STOP':
                if len(stack)!=1 or pos!=len(data)-1:raise FormatError('non-single result/trailing bytes')
                stopped=True;break
            else:raise FormatError('unsupported opcode '+n)
    except (ValueError,IndexError,TypeError,OverflowError) as e:
        if isinstance(e,FormatError):raise
        raise FormatError('malformed pickle syntax: '+str(e)) from e
    if not stopped:raise FormatError('missing STOP')
    return stack[0]
def global_name(x):
    return x.args if isinstance(x,Opaque) and x.kind=='global' else None
def reduction(x):
    if not isinstance(x,Opaque) or x.kind not in ('REDUCE','NEWOBJ','NEWOBJ_EX'):raise FormatError('not opaque object')
    return global_name(x.args[0]),x.args[1]
def dtype(x):
    name,args=reduction(x)
    if name!=('numpy','dtype') or not args or args[0] not in ('f8','<f8','>f8','=f8'):raise FormatError('unsupported dtype')
    s=x.state
    if not isinstance(s,tuple) or len(s)!=8 or s[0]!=3 or s[1] not in ('<','>') or s[2:5]!=(None,None,None) or s[5:]!=(-1,-1,0):raise FormatError('unsupported or ambiguous dtype state')
    endian=s[1]
    if args[0][0] in '<>' and args[0][0]!=endian:raise FormatError('conflicting dtype endian')
    return endian

def vector(x):
    if isinstance(x,(list,tuple)):
        if len(x)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in x):raise FormatError('nonfinite/non3-vector')
        return [float(v) for v in x]
    name,args=reduction(x)
    if name in (('numpy.core.numeric','_frombuffer'),('numpy._core.numeric','_frombuffer')):
        if len(args)!=4 or args[2]!=(3,) or args[3] not in ('C','F') or not isinstance(args[0],bytes) or len(args[0])!=24:raise FormatError('unsupported array shape/buffer')
        endian=dtype(args[1]);raw=args[0]
    elif name in (('numpy.core.multiarray','_reconstruct'),('numpy._core.multiarray','_reconstruct')):
        s=x.state
        if not isinstance(s,tuple) or len(s)!=5 or s[0]!=1 or s[1]!=(3,) or type(s[3])is not bool or not isinstance(s[4],bytes) or len(s[4])!=24:raise FormatError('unsupported ndarray state')
        endian=dtype(s[2]);raw=s[4]
    else:raise FormatError('unsupported vector constructor')
    return vector(struct.unpack(endian+'3d',raw))
def extract(data, expected_frame=None, expected_actor=None):
    """Extract inert numeric candidates; callers verify producer, checksum and original joins."""
    root=decode(data);name,args=reduction(root)
    if name!=('networkx.classes.digraph','DiGraph') or args!=() or not isinstance(root.state,dict):raise FormatError('not native DiGraph state')
    state=root.state;meta=state.get('graph');nodes=state.get('_node')
    if not isinstance(meta,dict) or not isinstance(nodes,dict):raise FormatError('missing graph/nodes')
    frame=meta.get('frame');time=meta.get('simulation_time_s')
    if type(frame)is not int or type(time)not in(int,float) or not math.isfinite(time):raise FormatError('missing finite original frame/time')
    if expected_frame is not None and frame!=expected_frame:raise FormatError('frame mismatch')
    out=[];seen=set()
    for native_name,attrs in nodes.items():
        if not isinstance(native_name,str) or not isinstance(attrs,dict):continue
        keys=['carla_acc_'+k for k in 'xyz']
        if not any(k in attrs for k in keys):continue
        if not all(k in attrs for k in keys):raise FormatError('partial acceleration')
        actor=attrs.get('entity_id')
        if type(actor)is not int or actor<=0 or actor in seen:raise FormatError('missing/duplicate actor identity')
        seen.add(actor);acc=vector([attrs[k] for k in keys]);forward=vector(attrs.get('forward'))
        if math.hypot(*forward[:2])<=1e-12:raise FormatError('degenerate horizontal forward')
        out.append({'native_name':native_name,'actor_id':actor,'frame':frame,'simulation_time_s':time,'acceleration_mps2':acc,'forward_vector':forward})
    if expected_actor is not None and not any(a['actor_id']==expected_actor for a in out):raise FormatError('expected actor absent')
    if not out:raise FormatError('no complete actor acceleration')
    return out
