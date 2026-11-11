"""Render the GGUF's own template when the native preset renderer cannot."""
import datetime,json
from jinja2.sandbox import ImmutableSandboxedEnvironment

def render(template,messages,bos_token='',eos_token=''):
    if not isinstance(template,str) or not template:
        raise ValueError('This model does not include a supported chat template.')
    if len(template)>1000000:raise ValueError('Chat template exceeds the supported size.')
    env=ImmutableSandboxedEnvironment(trim_blocks=True,lstrip_blocks=True,extensions=['jinja2.ext.loopcontrols'])
    def reject(message):raise ValueError(str(message))
    env.globals.update(raise_exception=reject,strftime_now=lambda fmt:datetime.datetime.now().strftime(fmt))
    env.filters['tojson']=lambda value,**kwargs:json.dumps(value,ensure_ascii=False,**kwargs)
    # Consecutive system instructions are one system turn for templates that require it.
    merged=[]
    for message in messages:
        item=dict(message)
        if merged and item['role']=='system' and merged[-1]['role']=='system':merged[-1]['content']+='\n\n'+item['content']
        else:merged.append(item)
    result=env.from_string(template).render(messages=merged,add_generation_prompt=True,enable_thinking=False,preserve_thinking=False,tools=None,bos_token=bos_token,eos_token=eos_token)
    if not result or len(result)>4000000:raise ValueError('Chat template produced an invalid prompt.')
    return result
