"""Bounded-memory reader/writer for saved Core scenes, preserving raw scene tokens."""
import json
import re


def scenes(path):
    decoder=json.JSONDecoder()
    with open(path) as stream:
        buffer=stream.read(1024*1024)
        head=re.match(r'\s*\{\s*"scenes"\s*:\s*\[',buffer)
        if head is None:raise ValueError('Expected a Core scenes document: '+str(path))
        buffer=buffer[head.end():];after=False
        while True:
            buffer=buffer.lstrip()
            if not buffer:
                buffer=stream.read(1024*1024)
                if not buffer:raise ValueError('Truncated trace')
                continue
            if buffer.startswith(']'):
                if not re.fullmatch(r'\]\s*\}\s*',buffer+stream.read()):raise ValueError('Unexpected trace suffix')
                return
            if after:
                if not buffer.startswith(','):raise ValueError('Missing scene separator')
                buffer=buffer[1:].lstrip()
            while True:
                try:scene,end=decoder.raw_decode(buffer);break
                except json.JSONDecodeError:
                    more=stream.read(1024*1024)
                    if not more:raise ValueError('Truncated/malformed scene')
                    buffer+=more
            raw=buffer[:end];buffer=buffer[end:];yield scene,raw;after=True


def replace_field(raw, name, value):
    matches=list(re.finditer('"'+re.escape(name)+'"\\s*:\\s*',raw))
    if len(matches)>1:raise ValueError('Ambiguous scene field '+name)
    encoded=json.dumps(value,separators=(',',':'),allow_nan=False)
    if not matches:return raw[:-1]+',"'+name+'":'+encoded+'}'
    match=matches[0];_,end=json.JSONDecoder().raw_decode(raw,match.end())
    return raw[:match.end()]+encoded+raw[end:]
