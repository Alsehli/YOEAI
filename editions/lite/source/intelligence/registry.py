"""Named capabilities, strict schemas and bounded execution; never shell text."""
from dataclasses import dataclass,field
import json,time,threading,concurrent.futures
from jsonschema import Draft202012Validator

class Cancelled(Exception):pass
class PermissionDenied(ValueError):pass

@dataclass
class Context:
    session:str
    request:str
    question:str
    history:list=field(default_factory=list)
    documents:list=field(default_factory=list)
    cancel:threading.Event=field(default_factory=threading.Event)
    deadline:float=field(default_factory=lambda:time.monotonic()+120)
    private_seen:bool=False
    approved:bool=False
    def check(self):
        if self.cancel.is_set():raise Cancelled('Stopped')
        if time.monotonic()>self.deadline:raise TimeoutError('Assistant time budget exceeded.')

@dataclass(frozen=True)
class Tool:
    name:str
    description:str
    inputs:dict
    outputs:dict
    handler:object
    permission:str='read'
    timeout:float=25
    limits:dict=field(default_factory=lambda:{'outputBytes':64000})
    approval:bool=False
    network:bool=False
    modifies:bool=False
    private:bool=False

class Registry:
    def __init__(self,proposal):self.tools={};self.proposal=proposal
    def add(self,tool):
        if tool.name in self.tools:raise ValueError('Duplicate tool name')
        Draft202012Validator.check_schema(tool.inputs);Draft202012Validator.check_schema(tool.outputs)
        self.tools[tool.name]=tool
    def describe(self):
        return [{'name':t.name,'description':t.description,'inputSchema':t.inputs,'outputSchema':t.outputs,'permission':t.permission,'timeout':t.timeout,'resourceLimits':t.limits,'approvalRequired':t.approval,'externalNetwork':t.network,'modifiesState':t.modifies} for t in self.tools.values()]
    def execute(self,name,args,ctx):
        ctx.check()
        if name not in self.tools:raise ValueError('Unknown assistant tool.')
        tool=self.tools[name];Draft202012Validator(tool.inputs).validate(args)
        if tool.approval and not ctx.approved:return {'approval':self.proposal(tool,args,ctx),'executed':False}
        if tool.network and ctx.private_seen and not ctx.approved:raise PermissionDenied('Private evidence cannot be used to create external searches. Ask a separate public question.')
        if tool.private:ctx.private_seen=True
        start=time.monotonic();result=tool.handler(args,ctx);ctx.check()
        Draft202012Validator(tool.outputs).validate(result)
        encoded=json.dumps(result,ensure_ascii=False).encode('utf8')
        if len(encoded)>tool.limits.get('outputBytes',64000):raise ValueError('Tool output exceeded its budget.')
        if time.monotonic()-start>tool.timeout:raise TimeoutError('Tool exceeded its cooperative stage deadline.')
        return result

def obj(properties,required=()):return {'type':'object','properties':properties,'required':list(required),'additionalProperties':False}
TEXT={'type':'string','minLength':1,'maxLength':1000}
RESULT={'type':'object'}
