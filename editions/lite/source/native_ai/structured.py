"""Constrained JSON syntax; callers retain their existing semantic schema checks."""
def schema_guidance(value):
 """Compact prompt guidance, never an authorization/schema validator.

 Windows plans repeat their complete object shape once per tool. Retain the
 common shape and enumerate each tool's parameter requirements without that
 duplication. Application validators still check the original complete schema.
 """
 if isinstance(value,list):return [schema_guidance(x)for x in value]
 if not isinstance(value,dict):return value
 result={k:schema_guidance(v)for k,v in value.items()}
 variants=value.get('anyOf')
 if value.get('properties') and isinstance(variants,list) and variants and all(isinstance(v,dict)and 'properties'in v and 'tool'in v['properties']and 'params'in v['properties']for v in variants):
  result.pop('anyOf',None)
  rules=[]
  for v in variants:
   params=v['properties']['params'];constraints={k:{a:b for a,b in p.items()if a!='type'}for k,p in params.get('properties',{}).items()if any(a!='type'for a in p)}
   rules.append({'tool':v['properties']['tool'],'allowedParams':list(params.get('properties',{})),'requiredParams':params.get('required',[]),'constraints':constraints})
  result['toolParameterRules']=rules
 return result
JSON_GRAMMAR=r'''
root ::= object ws
value ::= object | array | string | number | "true" | "false" | "null"
object ::= "{" ws (string ws ":" ws value ws ("," ws string ws ":" ws value ws)*)? "}"
array ::= "[" ws (value ws ("," ws value ws)*)? "]"
string ::= "\"" ([^"\\\x00-\x1F] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F]{4}))* "\""
number ::= "-"? ("0" | [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
ws ::= [ \t\n\r]*
'''
