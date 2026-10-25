"""Deterministic evidence checks and a deliberately small Python test interpreter.

No eval/exec, imports, calls, attributes, filesystem or subprocess access.
Unsupported Python is BLOCKED, never silently treated as tested.
"""
import ast, math, operator, re
from urllib.parse import urlsplit, urlunsplit

def evidence_sources(rows):
    sources=[]; seen=set()
    for row in rows[:20]:
        if not isinstance(row,dict):continue
        url=row.get('url','')
        if not isinstance(url,str):continue
        try:
            p=urlsplit(url)
            if p.scheme not in ('https','http') or not p.hostname or p.username or p.password:continue
            url=urlunsplit((p.scheme,p.netloc,p.path,p.query,''))
        except ValueError:continue
        if url in seen:continue
        seen.add(url)
        sources.append({'id':'S'+str(len(sources)+1),'title':str(row.get('title','Untitled'))[:250],
                        'url':url,'domain':p.hostname,'snippet':str(row.get('snippet',''))[:2000],
                        'publicationDate':'Unknown; not independently verified','evidenceType':'Search snippet only'})
    return sources

def audit_report(report,sources):
    allowed={s['url'] for s in sources}; removed=[]
    def link(m):
        value=m.group(0)
        suffix=''
        while value and value[-1] in '.,;:':suffix=value[-1]+suffix;value=value[:-1]
        if value in allowed:return value+suffix
        removed.append(value);return '[unverified link removed]'+suffix
    report=re.sub(r'https?://[^\s)\]>]+',link,report)
    ids={s['id'] for s in sources}
    def citation(m):
        terms=re.split(r'\s*[,;]\s*',m.group(0)[1:-1]); valid=True
        for term in terms:
            match=re.fullmatch(r'S(\d+)(?:\s*-\s*S(\d+))?',term)
            if not match:valid=False;break
            lo=int(match[1]);hi=int(match[2] or match[1])
            if not 1<=lo<=hi<=len(ids):valid=False;break
        if valid:return m.group(0)
        removed.append(m.group(0));return '[unsupported citation removed]'
    report=re.sub(r'\[S\d+[^\]\n]{0,100}\]',citation,report)
    return report,{'availableSources':len(sources),'independentDomains':len({s['domain'] for s in sources}),
                   'removedReferences':removed,'fullPagesReviewed':False,
                   'claimVerification':'Citation membership checked; factual accuracy is not guaranteed.'}

class Unsupported(ValueError):pass

def scalar(value):
    if type(value) not in (int,float,bool,str,type(None)):raise Unsupported('Only scalar values are supported.')
    if isinstance(value,str) and len(value)>2000:raise Unsupported('String limit exceeded.')
    if type(value) in (int,float) and (abs(value)>1e12 or not math.isfinite(value)):raise Unsupported('Numeric limit exceeded.')
    return value

def check_cases(cases):
    if not isinstance(cases,list) or not 1<=len(cases)<=12:raise ValueError('Use 1–12 explicit example cases.')
    for c in cases:
        if not isinstance(c,dict) or set(c)!={'file','function','args','expected'}:raise ValueError('Each case needs file, function, args and expected.')
        if not isinstance(c['file'],str) or not isinstance(c['function'],str) or not c['function'].isidentifier() or c['function'].startswith('_'):raise ValueError('Choose a named public Python function in an approved file.')
        if not isinstance(c['args'],list) or len(c['args'])>8:raise ValueError('Use at most eight scalar arguments.')
        for v in [*c['args'],c['expected']]:scalar(v)
    return cases

BIN={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod}
CMP={ast.Eq:operator.eq,ast.NotEq:operator.ne,ast.Lt:operator.lt,ast.LtE:operator.le,ast.Gt:operator.gt,ast.GtE:operator.ge}
ALLOWED=(ast.Module,ast.FunctionDef,ast.arguments,ast.arg,ast.Return,ast.Assign,ast.If,ast.Pass,ast.Expr,ast.Constant,ast.Name,ast.Load,ast.Store,ast.BinOp,ast.UnaryOp,ast.BoolOp,ast.Compare,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.FloorDiv,ast.Mod,ast.UAdd,ast.USub,ast.Not,ast.And,ast.Or,ast.Eq,ast.NotEq,ast.Lt,ast.LtE,ast.Gt,ast.GtE)

def example_test(text,case):
    """Interpret a supported function, without executing a Python module."""
    result={'file':case['file'],'function':case['function'],'args':case['args'],'expected':case['expected'],
            'test':'Restricted Python example (AST interpreter)'}
    try:
        tree=ast.parse(text); matches=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==case['function']]
        if len(matches)!=1:raise Unsupported('Function not found or duplicated.')
        fn=matches[0];nodes=list(ast.walk(fn))
        if len(nodes)>400 or any(not isinstance(n,ALLOWED) for n in nodes):raise Unsupported('Function uses unsupported Python syntax (calls, loops, imports and attributes are blocked).')
        a=fn.args
        if fn.decorator_list or fn.returns or getattr(fn,'type_params',[]) or a.vararg or a.kwarg or a.defaults or a.kwonlyargs or a.kw_defaults or any(x.annotation for x in [*a.posonlyargs,*a.args]):raise Unsupported('Decorators, annotations, defaults and variadic parameters are unsupported.')
        args=[*a.posonlyargs,*a.args]
        if len(args)!=len(case['args']):raise Unsupported('Argument count does not match.')
        env={x.arg:scalar(v) for x,v in zip(args,case['args'])};steps=0
        def expr(n):
            nonlocal steps
            steps+=1
            if steps>1000:raise Unsupported('Evaluation limit exceeded.')
            if isinstance(n,ast.Constant):return scalar(n.value)
            if isinstance(n,ast.Name):
                if n.id not in env:raise Unsupported('External/global names are unsupported.')
                return env[n.id]
            if isinstance(n,ast.BinOp):
                left,right=expr(n.left),expr(n.right)
                if type(left) not in (int,float) or type(right) not in (int,float):raise Unsupported('Arithmetic supports numbers only.')
                return scalar(BIN[type(n.op)](left,right))
            if isinstance(n,ast.UnaryOp):
                value=expr(n.operand)
                if isinstance(n.op,ast.Not):return not value
                if type(value) not in (int,float):raise Unsupported('Numeric unary operators require numbers.')
                return scalar(+value if isinstance(n.op,ast.UAdd) else -value)
            if isinstance(n,ast.Compare):
                left=expr(n.left)
                for op,r in zip(n.ops,n.comparators):
                    right=expr(r)
                    if not CMP[type(op)](left,right):return False
                    left=right
                return True
            if isinstance(n,ast.BoolOp):
                value=expr(n.values[0])
                for item in n.values[1:]:
                    if isinstance(n.op,ast.And) and not value or isinstance(n.op,ast.Or) and value:return value
                    value=expr(item)
                return value
            raise Unsupported('Expression is unsupported.')
        def block(body):
            for n in body:
                if isinstance(n,ast.Return):return True,expr(n.value) if n.value else None
                if isinstance(n,ast.Assign):
                    if len(n.targets)!=1 or not isinstance(n.targets[0],ast.Name):raise Unsupported('Only simple local assignment is supported.')
                    env[n.targets[0].id]=expr(n.value)
                elif isinstance(n,ast.If):
                    returned,value=block(n.body if expr(n.test) else n.orelse)
                    if returned:return True,value
                elif isinstance(n,ast.Pass):pass
                elif isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str):pass
                else:raise Unsupported('Statement is unsupported.')
            return False,None
        _,actual=block(fn.body);result.update(actual=scalar(actual),status='PASS' if actual==case['expected'] and type(actual)==type(case['expected']) else 'FAIL')
    except (Unsupported,SyntaxError,RecursionError) as e:result.update(status='BLOCKED',error=str(e))
    except (ArithmeticError,TypeError,KeyError) as e:result.update(status='FAIL',error=str(e))
    return result
