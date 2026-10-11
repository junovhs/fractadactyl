#!/usr/bin/env python3
"""PROB-21 research probe: Misiurewicz orbits and provisional shape predicates.

This Euclidean Steiner skeleton is NOT a Hubbard tree: regulated Julia arcs and
Bruin-Schleicher kneading reconstruction are unimplemented. Fail closed.
"""
import argparse
from fractions import Fraction
import json
import os
from pathlib import Path
import shlex
import mpmath as mp

V0 = ('-0.7432918908524302029316241585089040394625440130877230883413356446722846985935655895273743988748934502',
      '0.1312405523087976047708458738159648480193742492666251343726688732491323053181613282916110110463622922')
LIMITS = {
    'dendrite': '>=3 forks with >=2 edges each turning <0.35 radians',
    'spoke/backbone': 'tree weighted diameter >=65% of summed edge length',
    'filament': 'fork-to-fork edge >=8% of diameter',
    'tendril': 'edge turn >=pi/2 and length >=8% of diameter',
    'hook': 'leaf directly at fork with edge turn >=pi/2',
    'spindle': 'fork-to-fork edge >=16% of diameter, minibrots not tested',
    'galaxy': '>=3 p-step growing orbit radii, turns >=0.25 radians',
    'whirlpool': '>=4 spiral ladder points (also check viewport)',
}


def fmt(x, digits=30):
    return mp.nstr(x, digits)


def orbit(c, n):
    z, d = [mp.mpc(0)], [mp.mpc(0)]
    for _ in range(n):
        d.append(2*z[-1]*d[-1]+1)
        z.append(z[-1]*z[-1]+c)
    return z, d


def discover(c, max_q=32, max_p=8):
    z, _ = orbit(c, max_q+max_p)
    _, q, p = min((abs(z[q+p]-z[q]),q,p)
                  for q in range(1,max_q+1)
                  for p in range(1,max_p+1))
    return q,p


def refine(c,q,p,dps):
    if q<1 or p<1 or q+p>1024:
        raise ValueError('q,p positive and q+p <=1024 required')
    initial=c
    tol=mp.power(10,12-dps)
    for _ in range(48):
        z,d=orbit(c,q+p)
        f=z[q+p]-z[q]
        slope=d[q+p]-d[q]
        if abs(f)<tol:
            break
        if abs(slope)<tol:
            raise ValueError('singular root; decline')
        step=f/slope
        if not mp.isfinite(abs(step)) or abs(step)>mp.mpf('.05'):
            raise ValueError('Newton step too large; decline')
        c-=step
    else:
        raise ValueError('nonconvergent root; decline')
    z,d=orbit(c,q+p)
    if abs(z[q+p]-z[q])>=tol or abs(c-initial)>mp.mpf('.05'):
        raise ValueError('unverified root; decline')
    if any(abs(z[j+p]-z[j])<tol for j in range(q)):
        raise ValueError('non-minimal preperiod; decline')
    if any(p%j==0 and abs(z[q+j]-z[q])<tol for j in range(1,p)):
        raise ValueError('non-minimal period; decline')
    lam=mp.mpc(1)
    for j in range(q,q+p):
        lam*=2*z[j]
    if abs(lam)<=1+mp.mpf('1e-8'):
        raise ValueError('cycle not repelling; decline')
    return c,z[:q+p],d[:q+p],lam,abs(z[q+p]-z[q])


def angle_period(a):
    seen={}
    t=a%1
    for n in range(1024):
        if t in seen:
            return seen[t],n-seen[t]
        seen[t]=n
        t=2*t%1
    raise ValueError('angle period too large')


def angles_checked(raw,q,p):
    result=[]
    for s in raw:
        f=Fraction(s)
        pre,per=angle_period(f)
        if per!=p or pre not in (q-1,q):
            raise ValueError('external angle doubling type inconsistent with critical orbit')
        result.append(str(f))
    return result


def proxy_tree(z):
    """Euclidean MST and locally shorter Fermat junctions; NOT regulated arcs."""
    pts=list(z)
    edges=[]
    active={0}
    while len(active)<len(pts):
        _,a,b=min((abs(pts[a]-pts[b]),a,b) for a in sorted(active)
                  for b in range(len(pts)) if b not in active)
        edges.append((a,b))
        active.add(b)
    for v in range(len(z)):
        nbr=[b if a==v else a for a,b in edges if a==v or b==v]
        if len(nbr)!=2:
            continue
        a,b=nbr
        x=(pts[a]+pts[v]+pts[b])/3
        for _ in range(80):
            dist=[abs(x-t) for t in (pts[a],pts[v],pts[b])]
            if min(dist)<mp.mpf('1e-35'):
                break
            weights=[1/d for d in dist]
            y=sum(t*w for t,w in zip((pts[a],pts[v],pts[b]),weights))/sum(weights)
            if abs(y-x)<mp.mpf('1e-30'):
                x=y
                break
            x=y
        old=abs(pts[a]-pts[v])+abs(pts[b]-pts[v])
        new=abs(pts[a]-x)+abs(pts[v]-x)+abs(pts[b]-x)
        if new>=old-mp.mpf('1e-12')*max(old,1):
            continue
        k=len(pts)
        pts.append(x)
        edges=[(i,j) for i,j in edges if v not in (i,j)]+[(a,k),(b,k),(v,k)]
    return pts,edges


def diameter(graph):
    def walk(root):
        ds={root:mp.mpf(0)}
        prev={root:None}
        stack=[root]
        while stack:
            a=stack.pop()
            for b,length in graph[a]:
                if b not in ds:
                    ds[b]=ds[a]+length
                    prev[b]=a
                    stack.append(b)
        end=max(ds,key=lambda k:ds[k])
        return end,ds[end],prev
    a,_,_=walk(0)
    b,dist,prev=walk(a)
    path=[b]
    while path[-1]!=a:
        path.append(prev[path[-1]])
    return dist,path


def ladder(z,q,p):
    if q<3*p:
        return []
    values=[z[q-k*p]-z[q] for k in range(q//p,0,-1)]
    best=[]
    run=[]
    for x in values:
        if not run:
            run=[x]
        elif abs(x)>abs(run[-1])*mp.mpf('1.1') and abs(mp.arg(x/run[-1]))>=mp.mpf('.25'):
            run.append(x)
        else:
            if len(run)>len(best):
                best=run
            run=[x]
    return run if len(run)>len(best) else best


def shape_metrics(z,q,p,lam):
    pts,links=proxy_tree(z)
    graph={i:[] for i in range(len(pts))}
    for a,b in links:
        length=abs(pts[a]-pts[b])
        graph[a].append((b,length))
        graph[b].append((a,length))
    span,path=diameter(graph)
    length=sum((abs(pts[a]-pts[b]) for a,b in links),mp.mpf(0))
    forks={i for i in graph if len(graph[i])>=3}
    leaves={i for i in graph if len(graph[i])==1}
    base=z[q]
    nonzero=[abs(x-base) for x in z if x!=base]
    floor=max(mp.mpf('1e-30'),min(nonzero,default=mp.mpf(1))*mp.mpf('.01'))
    def turn(a,b):
        ra=abs(pts[a]-base)+floor
        rb=abs(pts[b]-base)+floor
        return abs(mp.arg(lam)*mp.log(ra/rb)/mp.log(abs(lam)))
    ed=[(a,b,abs(pts[a]-pts[b]),turn(a,b)) for a,b in links]
    forks_quiet=sum(sum(turn(v,u)<mp.mpf('.35') for u,d in graph[v])>=2 for v in forks)
    spiral=ladder(z,q,p)
    flags={
        'dendrite': forks_quiet>=3,
        'spoke/backbone': span>=mp.mpf('.65')*length,
        'filament': any(a in forks and b in forks and d>=mp.mpf('.08')*span for a,b,d,t in ed),
        'tendril': any(d>=mp.mpf('.08')*span and t>=mp.pi/2 for a,b,d,t in ed),
        'hook': any(any(u in forks and turn(u,v)>=mp.pi/2 for u,d in graph[v]) for v in leaves),
        'spindle': any(a in forks and b in forks and d>=mp.mpf('.16')*span for a,b,d,t in ed),
        'galaxy': len(spiral)>=3,
        'whirlpool': len(spiral)>=4,
    }
    measurements=dict(max_arms=max(len(graph[i]) for i in graph),forks=len(forks),
                      tree_length=fmt(length),diameter=fmt(span),diameter_path=path,
                      branch_points=[dict(node=i,arms=len(graph[i]),re=fmt(mp.re(pts[i])),
                                          im=fmt(mp.im(pts[i]))) for i in sorted(forks)],
                      edges=[dict(a=a,b=b,length=fmt(d),turn_rad=fmt(t)) for a,b,d,t in ed],
                      spiral_points=len(spiral))
    return flags,measurements,span,spiral


def build_case(name,re,im,q=None,p=None,dps=85,angles=()):
    with mp.workdps(dps):
        original=mp.mpc(re,im)
        if q is None:
            q,p=discover(original)
        c,z,d,lam,resid=refine(original,q,p,dps)
        checks=angles_checked(angles,q,p)
        flags,metrics,span,spiral=shape_metrics(z,q,p,lam)
        return dict(name=name,source=[str(re),str(im)],
                    point=[fmt(mp.re(c),dps-12),fmt(mp.im(c),dps-12)],
                    q=q,p=p,angles=checks,residual=fmt(resid),shift=fmt(abs(c-original)),
                    multiplier=[fmt(mp.re(lam),dps-12),fmt(mp.im(lam),dps-12)],
                    dz=[fmt(mp.re(d[q]),dps-12),fmt(mp.im(d[q]),dps-12)],
                    span=fmt(span),orbit=[[fmt(mp.re(t)),fmt(mp.im(t))] for t in z],
                    spiral=[[fmt(mp.re(t)),fmt(mp.im(t))] for t in spiral],
                    fires=flags,metrics=metrics)


def view(case,shape,positive,i,out):
    with mp.workdps(max(90,len(case['point'][0])+20)):
        c=mp.mpc(*case['point'])
        lam=mp.mpc(*case['multiplier'])
        dz=mp.mpc(*case['dz'])
        if abs(dz)<mp.mpf('1e-20'):
            return None
        k=i+2
        width=mp.mpf(case['span'])/abs(dz)/abs(lam)**k
        width*=mp.mpf('1.4') if positive else mp.mpf('20')
        if shape=='whirlpool':
            if len(case['spiral'])<4:
                return None
            points=[mp.mpc(*a) for a in case['spiral']]
            width=mp.mpf('2.6')*max(abs(a) for a in points[:4])/abs(dz)/abs(lam)**k
            if not positive:
                width/=100
        if width<=0 or not mp.isfinite(width):
            return None
        stem=f"{shape.replace('/','-')}-{case['name']}-{'yes' if positive else 'no'}-{i+1:02d}"
        return dict(shape=shape,predicted=positive,case=case['name'],depth=k,
                    re=fmt(mp.re(c),72),im=fmt(mp.im(c),72),width=fmt(width,72),
                    stem=stem,png=str(out/(stem+'.studio.png')))


def output(cases,out,sheet=None):
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    (out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    views=[]
    for shape in LIMITS:
        for wanted in (True,False):
            eligible=[x for x in cases if x['fires'][shape]==wanted]
            for i in range(6):
                if eligible:
                    v=view(eligible[i%len(eligible)],shape,wanted,i,out)
                    if v:
                        views.append(v)
    (out/'views.json').write_text(json.dumps(views,indent=2)+'\n')
    script=['#!/usr/bin/env bash','set -euo pipefail',
            'FD="'+'$'+'{FD:-target/release/fd}"','mkdir -p '+shlex.quote(str(out))]
    for v in views:
        f=out/(v['stem']+'.fds')
        script.append('"$FD" render --re '+shlex.quote(v['re'])+' --im '+shlex.quote(v['im'])+
                      ' --width '+shlex.quote(v['width'])+
                      ' --size 320x180 --iter 100000 --columns nu,de,normal -o '+shlex.quote(str(f)))
        script.append('"$FD" shade '+shlex.quote(str(f))+
                      ' --preset ice -o '+shlex.quote(str(out)))
    (out/'render.sh').write_text('\n'.join(script)+'\n')
    (out/'render.sh').chmod(0o755)
    dest=Path(sheet) if sheet else out/'contact-sheet.md'
    dest.parent.mkdir(parents=True,exist_ok=True)
    lines=['# PROB-21: proposed shape contact sheet','',
           '**Not a Hubbard-tree reconstruction.** The edges below are Euclidean',
           'Steiner chords; no regulated Julia arcs or dynamical rays were checked.',
           'A prediction is a provisional numeric predicate, NOT a ground-truth',
           'visual label. Images and owner votes remain pending.','',
           'For exact numeric parameters inspect cases.json and views.json.','']
    for case in cases:
        m=case['metrics']
        lines.append(f"- {case['name']}: q={case['q']} p={case['p']}; max candidate valence={m['max_arms']}, forks={m['forks']}; c={case['point']}, residual={case['residual']}")
    for shape,rule in LIMITS.items():
        subset=[v for v in views if v['shape']==shape]
        lines.extend(['',f'## {shape}','',f'New threshold: {rule}.','',
                      '| Predicted | Exact centre (re, im) | Exact width | Thumbnail | Owner agrees? |',
                      '|---|---|---|---|---|'])
        for v in subset:
            image=os.path.relpath(v['png'],dest.parent).replace(os.sep,'/')
            lines.append(f"| {'fires' if v['predicted'] else 'does not fire'} ({v['case']}, k={v['depth']}) | {v['re']}, {v['im']} | {v['width']} | ![]({image}) | pending |")
        if sum(v['predicted'] for v in subset)<6 or sum(not v['predicted'] for v in subset)<6:
            lines.extend(['','**Insufficient cases: do not fabricate positive or negative thumbnails.**'])
    lines.extend(['','## Established and new','',
                  'Established: exact critical-orbit recurrence, repelling multiplier;',
                  'Douady-Hubbard postcritical regulated trees and Bruin-Schleicher',
                  'kneading/arms; Tan Lei (1990) *asymptotic* local similarity.',
                  'New, unproved: Euclidean skeleton, edge turns, all eight shape',
                  'predicates and first-order parameter-space camera width estimates.',
                  'Missing: the true tree embedding, ray landing, minibrot census,',
                  'independent negative corpus, owner visual judgments. No Rust',
                  'shortcut is authorized without DEC-10 / DEC-17 gates.','',
                  'References: Douady-Hubbard Orsay Notes; Bruin-Schleicher (2008)',
                  'doi:10.1112/jlms/jdn033; Tan Lei (1990); Munafo Mu-Ency.',''])
    dest.write_text('\n'.join(lines))
    print(f'{len(views)} planned renders; owner review pending: {dest}')


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--point',nargs=2,required=True,metavar=('RE','IM'))
    ap.add_argument('--out',required=True)
    ap.add_argument('--preperiod',type=int)
    ap.add_argument('--period',type=int)
    ap.add_argument('--digits',type=int,default=85)
    ap.add_argument('--angles',nargs='*',default=[],
                    help='exact rational angles for doubling-type check; not angle-only solver')
    ap.add_argument('--catalog',action='store_true',help='add known -2, i and v0 seeds')
    ap.add_argument('--sheet',help='contact sheet path (default OUT/contact-sheet.md)')
    a=ap.parse_args(argv)
    if (a.preperiod is None)!=(a.period is None):
        ap.error('--preperiod and --period must both be supplied')
    if not 45<=a.digits<=1200:
        ap.error('--digits must be in 45..1200')
    seeds=[('point',*a.point,a.preperiod,a.period,a.angles)]
    if a.catalog:
        seeds.extend([('minus-two','-2','0',2,1,()),
                      ('i','0','1',2,2,()),('v0',*V0,24,2,())])
    cases=[]
    seen=set()
    try:
        for name,re,im,q,p,angles in seeds:
            if (re,im) in seen:
                continue
            seen.add((re,im))
            case=build_case(name,re,im,q,p,a.digits,angles)
            cases.append(case)
            print(name,case['q'],case['p'],case['metrics']['max_arms'],case['residual'])
        output(cases,a.out,a.sheet)
    except (ValueError,ZeroDivisionError) as e:
        ap.error(str(e))


if __name__=='__main__':
    main()
