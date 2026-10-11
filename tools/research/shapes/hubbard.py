#!/usr/bin/env python3
"""PROB-21: angle-seeded abstract Hubbard-tree/viewport shape research.

The triod map is the Bruin–Kaffl–Schleicher combinatorial construction.
Combinatorial incidences are exact for a correctly identified landing angle;
ray-to-parameter association and Euclidean placements are numerical estimates.
There are no production shortcuts or inferred owner approvals.
"""
import argparse
from fractions import Fraction
from itertools import combinations
import json
from pathlib import Path
import shlex

import mpmath as mp

V0 = ('-0.7432918908524302029316241585089040394625440130877230883413356446722846985935655895273743988748934502',
      '0.1312405523087976047708458738159648480193742492666251343726688732491323053181613282916110110463622922')
# New, falsifiable visual hypotheses, not established terms of Hubbard-tree theory.
LIMITS = {
    'dendrite': 'at least 1 fork, max edge turn < 0.7 rad, width contains >= 3 arms',
    'spoke/backbone': 'longest tree path >= 0.52 of tree chord sum, width covers path',
    'filament': 'a fork-to-fork path, at least 0.06 of tree span, width frames the path',
    'tendril': 'edge rotation >= 0.6 rad over a view-scaled radial octave',
    'hook': 'terminal arm at fork, edge rotation >= 0.8 rad, width frames arm',
    'spindle': 'a pair of forks joined by path >= 0.09 of span, width frames path',
    'galaxy': 'q >= 6, >=2 forks; >=3 multiplier-predicted scale levels; abs(arg(lambda)) >=0.25 rad',
    'whirlpool': 'q >=8, >=2 forks, >=4 predicted scale levels and >=0.7 levels/log decade',
}


def fmt(x, digits=36):
    return mp.nstr(x, digits)


def orbit(c, n):
    z = [mp.mpc(0)]
    d = [mp.mpc(0)]
    for _ in range(n):
        d.append(2*z[-1]*d[-1]+1)
        z.append(z[-1]*z[-1]+c)
    return z, d


def discover(c, max_q=32, max_p=8):
    z, _ = orbit(c, max_q+max_p)
    _, q, p = min((abs(z[q+p]-z[q]),q,p) for q in range(1,max_q+1)
                  for p in range(1,max_p+1))
    return q,p


def refine(c,q,p,dps,limit='0.05'):
    if q < 1 or p < 1 or q+p > 1024:
        raise ValueError('q,p must be positive with sum <= 1024')
    initial = c
    tol = mp.power(10,12-dps)
    for _ in range(45):
        z,d = orbit(c,q+p)
        f,slope = z[q+p]-z[q],d[q+p]-d[q]
        if abs(f) < tol:
            break
        if abs(slope) < tol:
            raise ValueError('singular root: decline')
        step = f/slope
        if not mp.isfinite(abs(step)) or abs(step)>mp.mpf(limit):
            raise ValueError('Newton step outside landing neighborhood: decline')
        c -= step
    else:
        raise ValueError('Newton failed: decline')
    z,d = orbit(c,q+p)
    if abs(z[q+p]-z[q]) >= tol or abs(c-initial) > mp.mpf(limit):
        raise ValueError('root residual/displacement: decline')
    # Reduce the true orbit, not the ray's preperiod or period (they may differ).
    for qq in range(1,q+1):
        if abs(z[qq+p]-z[qq])<tol:
            q=qq
            break
    for pp in range(1,p+1):
        if p%pp==0 and abs(z[q+pp]-z[q])<tol:
            p=pp
            break
    lam = mp.mpc(1)
    for i in range(q,q+p):
        lam *= 2*z[i]
    if abs(lam) <= 1+mp.mpf('1e-8'):
        raise ValueError('non-repelling cycle: decline')
    return c,z[:q+p],d[:q+p],lam,abs(z[q+p]-z[q]),q,p


def angle_period(a):
    seen={}
    t=a%1
    for n in range(1025):
        if t in seen:
            return seen[t],n-seen[t]
        seen[t]=n
        t=2*t%1
    raise ValueError('angle has period over 1024')


def kneading(angle):
    """Critical value itinerary under the critical-ray semicircle partition."""
    a=Fraction(angle)%1
    pre,period=angle_period(a)
    low,high=a/2,(a+1)/2
    chars=[]
    t=a
    for _ in range(pre+period):
        chars.append('*' if t in (low,high) else ('1' if low<t<high else '0'))
        t=2*t%1
    if '*' in chars:
        raise ValueError('critical value ray hits partition boundary: decline')
    return Word(''.join(chars[:pre]), ''.join(chars[pre:]))


class Word:
    """Eventually periodic symbolic address, with exact finite description."""
    def __init__(self, before, period):
        if not period:
            raise ValueError('empty cycle')
        self.before,self.period=before,period

    def at(self, i):
        if i<len(self.before):
            return self.before[i]
        return self.period[(i-len(self.before))%len(self.period)]

    def signature(self, length):
        return ''.join(self.at(k) for k in range(length))

    def shift(self,n):
        if n<len(self.before):
            return Word(self.before[n:],self.period)
        off=(n-len(self.before))%len(self.period)
        return Word('',self.period[off:]+self.period[:off])

    def __repr__(self):
        return self.before+'('+self.period+')'


def triod(a,b,c,nu,cap=4096):
    """Formal triod/majority-vote map (BKS 2009, Proposition 3.5).

    Returns a median itinerary. A repeated formal state gives an eventual
    periodic branch point; a 0,* ,1 stop gives a precritical median.
    """
    current=[a,b,c]
    history={}
    voted=[]
    for k in range(cap):
        sig=tuple(repr(s) for s in current)
        if sig in history:
            start=history[sig]
            return Word(''.join(voted[:start]), ''.join(voted[start:]))
        history[sig]=k
        symbols=[w.at(0) for w in current]
        if set(symbols)=={'0','1','*'}:
            return Word(''.join(voted)+'*'+nu.before,nu.period)
        major='1' if symbols.count('1')>=2 else '0' if symbols.count('0')>=2 else None
        if major is None:
            if symbols.count('*')>=2:
                raise ValueError('ambiguous triod with two critical points: decline')
            major=next(v for v in symbols if v!='*')
        voted.append(major)
        current=[nu if symbol!=major and symbol!='*' else word.shift(1)
                 for word,symbol in zip(current,symbols)]
    raise ValueError('triod iteration cap reached: decline')


def abstract_tree(angle,q,p):
    """Incidence graph from triod medians, not geometric chord minimization."""
    nu=kneading(angle)
    seq=[Word('*'+nu.before,nu.period)]+[nu.shift(j) for j in range(q+p-1)]
    siglen=max(96,8*(q+p+len(nu.before)+len(nu.period)))
    def key(w):return w.signature(siglen)
    nodes={key(w):dict(symbol=repr(w), orbit=i) for i,w in enumerate(seq)}
    words={key(w):w for w in seq}
    if len(nodes)!=len(seq):
        raise ValueError('angle itinerary collapses distinct critical orbit points: decline')
    # Add all triod medians of postcritical points. Closure may require medians of
    # newly discovered branch points; expand until no new marked points occur.
    for _ in range(8):
        before=len(words)
        if before>96:
            raise ValueError('more than 96 abstract tree nodes: decline')
        for a,b,c in combinations(list(words),3):
            middle=triod(words[a],words[b],words[c],nu)
            k=key(middle)
            if k not in words:
                words[k]=middle
                nodes[k]=dict(symbol=repr(middle),orbit=None)
        if len(words)==before:
            break
    else:
        raise ValueError('median closure not reached: decline')
    # Two vertices are adjacent iff no third marked vertex is on their arc.
    # Evaluate median relation directly; avoids embedding-dependent triangulation.
    names=list(words)
    between={}
    for a,b,c in combinations(names,3):
        med=key(triod(words[a],words[b],words[c],nu))
        for x,y,z in ((a,b,c),(a,c,b),(b,c,a)):
            between[frozenset((x,y,z))]=med
    edges=[]
    for a,b in combinations(names,2):
        if not any(between[frozenset((a,b,t))]==t for t in names if t not in (a,b)):
            edges.append((a,b))
    if len(edges)!=len(names)-1:
        raise ValueError('inconsistent abstract tree incidence: decline')
    neighbors={k:[] for k in names}
    for a,b in edges:
        neighbors[a].append(b)
        neighbors[b].append(a)
    if not names or len(set(names))!=len(names):
        raise ValueError('bad tree: decline')
    visited=set(); pending=[names[0]]
    while pending:
        k=pending.pop()
        if k in visited:continue
        visited.add(k);pending.extend(neighbors[k])
    if len(visited)!=len(names):
        raise ValueError('disconnected tree: decline')
    ids={k:i for i,k in enumerate(names)}
    return ([dict(id=ids[k], arms=len(neighbors[k]), **nodes[k]) for k in names],
            [(ids[a],ids[b]) for a,b in edges],repr(nu))


def ray_landing(a,dps=65,steps=370):
    """Follow a parameter ray by dc/dlog|Phi_M|=2^(n-1) z_n/z'_n.

    The extrapolated landing is only a seed. Newton and orbit residual then
    verify a root; they do NOT certify the ray actually lands at that root.
    """
    with mp.workdps(dps):
        theta=Fraction(a)%1
        phi=2*mp.pi*mp.mpf(theta.numerator)/theta.denominator
        t=mp.mpf(4)
        c=mp.exp(t+1j*phi)-mp.mpf('.5')
        for _ in range(8):
            zz,dd=orbit(c,12)
            z,d=zz[-1],dd[-1]
            e=2**11
            lifted=mp.arg(z)+2*mp.pi*mp.nint((e*phi-mp.arg(z))/(2*mp.pi))
            err=(mp.log(abs(z))+1j*lifted)/e-(t+1j*phi)
            c-=err*e*z/d
        def speed(at, potential):
            n=min(64,max(9,int(mp.ceil(-mp.log(potential,2)))+8))
            zz,dd=orbit(at,n)
            z,d=zz[-1],dd[-1]
            if abs(d)==0 or abs(z)<2:
                raise ValueError('ray trace entered critical basin: decline')
            return mp.power(2,n-1)*z/d
        for _ in range(steps):
            following=t*mp.mpf('.95')
            h=following-t
            k1=speed(c,t)
            k2=speed(c+h*k1/2,t+h/2)
            k3=speed(c+h*k2/2,t+h/2)
            k4=speed(c+h*k3,following)
            c+=h*(k1+2*k2+2*k3+k4)/6
            t=following
        return c


def spiral(z,q,p):
    if q<3*p:
        return []
    cycle=z[q]
    points=[z[q-k*p]-cycle for k in range(q//p,0,-1)]
    # Consecutive inverse-cycle landings shrink radially with approximately
    # the multiplier's argument. A finite portion of the critical orbit only.
    best=[]; run=[]
    for point in points:
        if abs(point)==0:continue
        if run and not (abs(point)>abs(run[-1])*mp.mpf('1.04') and
                        abs(mp.arg(point/run[-1]))>mp.mpf('.15')):
            if len(run)>len(best):best=run
            run=[]
        run.append(point)
    return run if len(run)>len(best) else best


def geometry(tree,edges,z,lam,q,p):
    """Chord scale is only a lower bound, NOT regulated-arc length."""
    coords={t['id']:z[t['orbit']] if t['orbit'] is not None else None for t in tree}
    # Estimated branch placement: geometric mean of the three nearest orbit
    # vertices *in the combinatorial tree*, not a Steiner reconstruction.
    adj={t['id']:[] for t in tree}
    for a,b in edges:adj[a].append(b);adj[b].append(a)
    for id_,v in list(coords.items()):
        if v is not None:continue
        distances=[]
        for t in tree:
            if t['orbit'] is None:continue
            queue=[(id_,0)]; seen=set()
            while queue:
                k,d=queue.pop(0)
                if k in seen:continue
                seen.add(k)
                if k==t['id']:
                    distances.append((d,t['id']))
                    break
                queue.extend((b,d+1) for b in adj[k] if b not in seen)
        closest=sorted(distances)[:3]
        coords[id_]=sum((coords[j] for d,j in closest),mp.mpc(0))/len(closest)
    ed=[]
    for a,b in edges:
        d=abs(coords[a]-coords[b])
        ed.append(dict(a=a,b=b,length=fmt(d)))
    base=z[q]
    radii=[abs(x-base) for x in coords.values() if abs(x-base)>mp.mpf('1e-70')]
    floor=min(radii,default=mp.mpf('.01'))*mp.mpf('.01')
    total=sum((mp.mpf(e['length']) for e in ed),mp.mpf(0))
    for e in ed:
        ra=abs(coords[e['a']]-base)+floor
        rb=abs(coords[e['b']]-base)+floor
        # Research proposal: multiplier rotation per log radius, not canonical
        # angular transport along a regulated Julia arc.
        e['turn_rad']=fmt(abs(mp.arg(lam)*mp.log(ra/rb)/mp.log(abs(lam))))
    def walk(root):
        dist={root:mp.mpf(0)};prev={root:None}; stack=[root]
        while stack:
            v=stack.pop()
            for n in adj[v]:
                if n not in dist:
                    e=next(e for e in ed if {e['a'],e['b']}=={v,n})
                    dist[n]=dist[v]+mp.mpf(e['length'])
                    prev[n]=v;stack.append(n)
        endpoint=max(dist,key=dist.get)
        return endpoint,dist[endpoint],prev
    a,_,_=walk(tree[0]['id']);b,span,prev=walk(a)
    path=[b]
    while path[-1]!=a:path.append(prev[path[-1]])
    return dict(edges=ed,total=fmt(total),span=fmt(span),path=path,
                branch_points=[t for t in tree if t['arms']>=3],
                max_arms=max(t['arms'] for t in tree)),coords


def build_case(name,re,im,q=None,p=None,dps=80,angle=None,ray=False):
    with mp.workdps(dps):
        c0=mp.mpc(re,im)
        if q is None or p is None:q,p=discover(c0)
        c,z,d,lam,res,q,p=refine(c0,q,p,dps,limit='.12' if ray else '.05')
        status='no verified parameter ray supplied'
        nodes=[];edges=[];structure={}
        if angle is not None:
            angle=Fraction(angle)
            aq,ap=angle_period(angle)
            if aq==0:
                raise ValueError('external angle is periodic, not Misiurewicz')
            if aq>q or ap%p!=0:
                raise ValueError('angle doubling period incompatible with orbit: decline')
            nodes,edges,kn=abstract_tree(angle,q,p)
            structure,coords=geometry(nodes,edges,z,lam,q,p)
            status='abstract combinatorial incidence from angle; landing not independently certified'
        else:
            # Do not substitute a Euclidean Steiner tree when ray data is missing.
            span=max(abs(x-y) for x in z for y in z)
            structure=dict(span=fmt(span),total=fmt(span),max_arms=None,
                           branch_points=[],edges=[],path=[])
            kn=None
        levels=spiral(z,q,p)
        return dict(name=name,point=[fmt(mp.re(c),dps-15),fmt(mp.im(c),dps-15)],
                    q=q,p=p,angle=str(angle) if angle is not None else None,
                    angle_status=status,kneading=kn,residual=fmt(res),shift=fmt(abs(c-c0)),
                    multiplier=[fmt(mp.re(lam),dps-15),fmt(mp.im(lam),dps-15)],
                    dz=[fmt(mp.re(d[q]),dps-15),fmt(mp.im(d[q]),dps-15)],
                    nodes=nodes,tree_edges=edges,metrics=structure,
                    spiral=[[fmt(mp.re(x)),fmt(mp.im(x))] for x in levels])


def corpus(dps=80,max_angles=120):
    """Distinct Misiurewicz parameters seeded by rational parameter rays."""
    cases=[]; seen=set()
    pool=[]
    for aq in range(1,9):
        for ap in range(1,5):
            denominator=(1<<aq)*((1<<ap)-1)
            for n in range(1,denominator):
                if n%2==0:continue
                a=Fraction(n,denominator)
                if angle_period(a)!=(aq,ap):continue
                pool.append((aq,ap,a))
    # Fixed strided sample across angle types (not N copies of three points).
    pool.sort(key=lambda entry:(entry[0]+entry[1],entry[1],entry[2]))
    stride=max(1,len(pool)//max_angles) if max_angles else 1
    selected=pool[::stride][:max_angles] if max_angles else []
    for aq,ap,a in selected:
        try:
            seed=ray_landing(a,dps=max(55,dps-10))
            candidate=build_case('ray-'+str(a).replace('/','-'),fmt(mp.re(seed),dps-10),
                                 fmt(mp.im(seed),dps-10),aq+1,ap,dps,a,ray=True)
        except (ValueError,ZeroDivisionError,OverflowError):
            continue
        c=mp.mpc(*candidate['point'])
        if abs(c)>2.3:continue
        key=(candidate['q'],candidate['p'],fmt(mp.re(c),22),fmt(mp.im(c),22))
        if key in seen:continue
        seen.add(key)
        cases.append(candidate)
    return cases


def metrics_for_view(case,width,shape):
    """Evaluate rule on this width, never re-use an input-wide boolean."""
    with mp.workdps(85):
        span=mp.mpf(case['metrics']['span'])
        dz=abs(mp.mpc(*case['dz']))
        lam=mp.mpc(*case['multiplier'])
        scale=span/max(dz,mp.mpf('1e-80'))
        ratio=mp.mpf(width)/max(scale,mp.mpf('1e-1000'))
        forks=len(case['metrics']['branch_points'])
        branches=case['metrics']['max_arms'] or 0
        edges=case['metrics']['edges']
        length=mp.mpf(case['metrics']['total'])
        chord_span=span
        # Useful visible range is roughly 0.35..5 times local feature width.
        frame=mp.mpf('.01999')<=ratio<=mp.mpf('5.00001')
        model_levels=max(0,int(mp.floor(mp.log(1/max(ratio,mp.mpf('1e-999')))/mp.log(abs(lam))))) if ratio<1 else 0
        density=1/mp.log10(abs(lam))
        turn=abs(mp.arg(lam))*max(mp.mpf(0),-mp.log(max(ratio,mp.mpf('1e-999')))/mp.log(abs(lam)))
        levels=len(case['spiral'])
        chord_turn=max([mp.mpf(e['turn_rad']) for e in edges] or [mp.mpf(0)])
        fork_ids={b['id'] for b in case['metrics']['branch_points']}
        pairs=sum(1 for e in edges if e['a'] in fork_ids and e['b'] in fork_ids and
                  mp.mpf(e['length'])>=mp.mpf('.06')*chord_span)
        leaf_fork=sum(1 for e in edges if (e['a'] in fork_ids) != (e['b'] in fork_ids))
        booleans={
            'dendrite':frame and forks>=1 and branches>=3 and chord_turn<mp.mpf('.7'),
            'spoke/backbone':frame and length>0 and chord_span/length>=mp.mpf('.52'),
            'filament':frame and pairs>=1,
            'tendril':frame and turn>=mp.mpf('.6'),
            'hook':frame and leaf_fork>=1 and turn>=mp.mpf('.8'),
            'spindle':frame and pairs>=1 and any(mp.mpf(e['length'])>=mp.mpf('.09')*chord_span for e in edges if e['a'] in fork_ids and e['b'] in fork_ids),
            'galaxy':case['q']>=6 and forks>=2 and model_levels>=3 and abs(mp.arg(lam))>=mp.mpf('.25'),
            'whirlpool':case['q']>=8 and forks>=2 and model_levels>=4 and density>=mp.mpf('.7'),
        }
        return booleans[shape], dict(fork_count=forks,max_arms=branches,
              paired_fork_edges=pairs,spiral_levels=levels,
              predicted_turn_rad=fmt(turn,9),modeled_levels=model_levels,modeled_density=fmt(density,8),edge_turn_max_rad=fmt(chord_turn,9),
              width_over_local_scale=fmt(ratio,9),frame_gate=bool(frame))


def sample_views(cases,out):
    """Never present an ineligible or duplicated frame as visual evidence."""
    all_views=[];used=set()
    for shape in LIMITS:
        for positive in (True,False):
            collected=0
            # One camera per independent parameter, except when the corpus is
            # insufficient (then a second scale at a point may be reviewed).
            for pass_no in range(2):
                for case in cases:
                    if collected==6:break
                    if pass_no==1 and not any(v['case']==case['name'] and v['shape']==shape
                                               and v['expected']==positive for v in all_views):
                        continue
                    with mp.workdps(85):
                        scale=mp.mpf(case['metrics']['span'])/abs(mp.mpc(*case['dz']))
                        if scale<=0:continue
                        lam=abs(mp.mpc(*case['multiplier']))
                        mult=(lam**(-mp.mpf(5 if shape=='whirlpool' else 4))
                              if shape in ('galaxy','whirlpool') else
                              mp.mpf('.06')+collected*mp.mpf('.015')) if positive else (
                              mp.mpf('15')+mp.mpf(collected)*mp.mpf('3'))
                        if pass_no:mult*=mp.mpf('1.02')
                        width=scale*mult
                        val,values=metrics_for_view(case,width,shape)
                        if val!=positive:continue
                        sig=(case['point'][0],case['point'][1],fmt(width,55))
                        if sig in used:continue
                        used.add(sig)
                        stem=f'{shape.replace("/","-")}-{case["name"]}-{"yes" if positive else "no"}-{collected+1:02d}'
                        all_views.append(dict(stem=stem,shape=shape,expected=val,
                             case=case['name'],point=case['point'],re=case['point'][0],
                             im=case['point'][1],width=fmt(width,72),angle=case['angle'],
                             q=case['q'],p=case['p'],threshold=LIMITS[shape],values=values,
                             image=f'img/{stem}.studio.png'))
                        collected+=1
                if collected==6:break
    return all_views


def output(cases,out,sheet=None):
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    (out/'img').mkdir(parents=True,exist_ok=True)
    views=sample_views(cases,out)
    (out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    (out/'views.json').write_text(json.dumps(views,indent=2)+'\n')
    script=['#!/usr/bin/env bash','set -euo pipefail','FD="${FD:-target/release/fd}"',
            'mkdir -p '+shlex.quote(str(out/'img'))]
    for v in views:
        f=out/'img'/(v['stem']+'.fds')
        script.append('"$FD" render --re '+shlex.quote(v['re'])+' --im '+shlex.quote(v['im'])+
                      ' --width '+shlex.quote(v['width'])+
                      ' --size 320x180 --iter 100000 --columns nu,de,normal -o '+shlex.quote(str(f)))
        script.append('"$FD" shade '+shlex.quote(str(f))+
                      ' --preset ice -o '+shlex.quote(str(out/'img')))
    (out/'render.sh').write_text('\n'.join(script)+'\n')
    (out/'render.sh').chmod(0o755)
    dest=Path(sheet) if sheet else out/'contact-sheet.md'
    dest.parent.mkdir(parents=True,exist_ok=True)
    def img_path(v):
        return Path(__import__('os').path.relpath(out/v['image'],dest.parent)).as_posix()
    lines=['# PROB-21: owner review of tree-derived *hypotheses*','',
           '**No owner votes yet.** “Fires” means only that the declared new,',
           'width-dependent predicate evaluates true. A wrong thumbnail must be rejected.',
           'The coordinates and widths are decimal strings, not f64.',
           '',f'Unique parameter points: {len(cases)}. Unique camera views: {len(views)}.',
           'All images are 320x180 and `render.sh` writes `img/*.studio.png` here.','',
           'The abstract combinatorial graph uses BKS triod medians from exact',
           'rational external-angle itineraries. Parameter-ray tracing and landing',
           'association are numerical (not certified). Tree edges are **chord lower',
           'bounds**, not geometrically traced Julia regulated arcs. Rotation per',
           'edge is the new multiplier log-radius model; not a canonical Julia-arc twist.',
           '', '## Owner voting', '',
           'Mark agree/reject/unsure in the final column. The target is 6 genuinely',
           'agreeing yes views and 6 genuinely rejecting no views for >=6 of 8 labels.', '']
    for shape,rule in LIMITS.items():
        subset=[v for v in views if v['shape']==shape]
        yes=sum(v['expected'] for v in subset);no=len(subset)-yes
        lines += [f'## {shape} ({yes} fires / {no} not)','',
                  '**New proposed threshold:** '+rule, '',
                  '| Vote | Predicted / source | Image 320×180 | Predicate metrics / exact width / centre | Owner vote |',
                  '|---|---|---|---|---|']
        for v in subset:
            vals=', '.join(f'{k}={x}' for k,x in v['values'].items())
            lines.append(f"| □ | {'yes' if v['expected'] else 'no'}; {v['case']}, angle={v['angle']} | ![]({img_path(v)}) | {vals}; width=`{v['width']}`; c=(`{v['re']}`, `{v['im']}`) | pending |")
        if yes<6 or no<6:lines+=['','**INSUFFICIENT — not a passing shape.**']
        lines.append('')
    lines += ['## Established vs new','',
        '**Established:** Douady–Hubbard: Hubbard tree = regulated Julia arcs',
        'connecting the finite critical orbit. Bruin–Kaffl–Schleicher (2009),',
        'Proposition 3.5: majority/chopping triod algorithm determines incidence',
        'and branch points from kneading. Bruin–Schleicher (2008): arm dynamics',
        'and admissibility. Tan Lei (1990): asymptotic parameter/Julia similarity',
        'at Misiurewicz points, not equality at finite width.','',
        '**New (unproved):** eight named thresholds; chord lengths in dynamical',
        'state units divided by `|dz_q/dc|` as a first-order parameter scale;',
        'log-radius edge rotations from `arg(lambda)/log(|lambda|)`; using',
        'multiplier-extrapolated (not observed) scale levels for galaxy/whirlpool density.',
        'No spindle criterion actually detects minibrots; no galaxy hierarchy',
        'of independent nested spirals is proven. The owner must judge these.',
        '', '**Numerical contracts:** root Newton residual and repelling cycle are',
        'checked, and failed ray/refinement/triod cases are *excluded* (not',
        'silently converted to positive examples). Ray landing itself is not',
        'certified; branch coordinates and chord lengths are preliminary.',
        'No Rust fast path is proposed (DEC-10/DEC-17 do not apply as promotion).',
        '', 'References: [Orsay notes](https://pi.math.cornell.edu/~hubbard/OrsayEnglish.pdf);',
        '[Bruin–Kaffl–Schleicher 2009](https://doi.org/10.4064/fm202-3-4);',
        '[Bruin–Schleicher 2008](https://doi.org/10.1112/jlms/jdn033);',
        '[Tan Lei 1990](https://doi.org/10.1007/BF02097356);',
        '[Munafo Mu-Ency](https://www.mrob.com/pub/muency.html).','']
    dest.write_text('\n'.join(lines))
    print(f'{len(cases)} independent Misiurewicz parameters, {len(views)} distinct view plans; {dest}')


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--point',nargs=2,metavar=('RE','IM'),required=True)
    ap.add_argument('--out',default='docs/research/shapes')
    ap.add_argument('--sheet',default=None)
    ap.add_argument('--preperiod',type=int)
    ap.add_argument('--period',type=int)
    ap.add_argument('--angles',nargs='*',default=[])
    ap.add_argument('--catalog',action='store_true')
    ap.add_argument('--max-rays',type=int,default=24)
    ap.add_argument('--digits',type=int,default=80)
    a=ap.parse_args(argv)
    if (a.preperiod is None)!=(a.period is None):ap.error('preperiod and period must both be set')
    if not 45<=a.digits<=350:ap.error('digits must be between 45 and 350')
    if not 0<=a.max_rays<=24:ap.error('max-rays must be between 0 and 24 (bounded research corpus)')
    try:
        angle=a.angles[0] if a.angles else None
        cases=[build_case('point',*a.point,a.preperiod,a.period,a.digits,angle)]
        if a.catalog:
            cases += [build_case('minus-two','-2','0',2,1,a.digits,'1/2'),
                      build_case('i','0','1',2,2,a.digits,'1/6'),
                      build_case('v0',*V0,24,2,a.digits)]
            cases += corpus(a.digits,a.max_rays)
        unique={}
        for c in cases:unique[tuple(c['point'])]=c
        output(list(unique.values()),a.out,a.sheet)
    except (ValueError,ZeroDivisionError,OverflowError) as error:
        ap.error(str(error))


if __name__=='__main__':
    main()
