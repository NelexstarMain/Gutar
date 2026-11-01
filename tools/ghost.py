#!/usr/bin/env python3
"""ghost.py - miara "duchów": ile razy w ramce pojawia się dźwięk, którego nie ma w żadnym chwycie granym w tym segmencie
(ani w poprzednim przez pierwsze 0,8 s). Do oceny śledzenia ręki. Użycie: ghost.py <korpus> <katalog_wyników>"""
import sys, json, glob, os
def run(corpus, resdir):
    fr_tot=0; ghost=0; true_hit=0; gh_pitches=0; seg_n=0; seg_with=0
    for tf in sorted(glob.glob(corpus+'/strum_*.truth.json')):
        t=json.load(open(tf)); r=json.load(open(os.path.join(resdir,t['id']+'.json')))
        win=r.get('winSec',0.3715)
        for i,c in enumerate(t['chords']):
            cur=set(n['midi'] for n in t['notes'] if c['t0']-0.05<=n['t0']<=c['t1'])
            prev=set(n['midi'] for n in t['notes'] if i>0 and t['chords'][i-1]['t0']-0.05<=n['t0']<=t['chords'][i-1]['t1'])
            seen=set()
            for f in r['frames']:
                tc=f['t']-win/2
                if c['t0']+0.45<=f['t']<=c['t1']-0.05 and not f['silent']:
                    for m in f['notes']:
                        fr_tot+=1
                        if m in cur: true_hit+=1
                        elif m in prev and f['t']<c['t0']+0.8: pass
                        else: ghost+=1; seen.add(m)
            gh_pitches+=len(seen); seg_n+=1; seg_with+= bool(seen)
    print("%-10s nuty-w-ramkach %d  duchy %d (%.2f%%)  segmentów z duchem %d/%d  rozróżnialnych wysokości-duchów %d"%(os.path.basename(resdir),fr_tot,ghost,100*ghost/fr_tot,seg_with,seg_n,gh_pitches))
run(sys.argv[1], sys.argv[2])
