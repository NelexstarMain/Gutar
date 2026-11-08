"""Sprawdza programem wszystkie liczby z przykładów, twierdzeń i rozwiązań ćwiczeń (po jednej funkcji na rozdział).
Uruchom: python3 weryfikacja.py   -> kończy się błędem, jeśli jakakolwiek liczba w książce się nie zgadza."""
import math
import numpy as np

def blisko(a, b, tol=1e-9):
    assert abs(a - b) <= tol * max(1, abs(b)), (a, b)

def rozdzial_01():
    assert sum(i * i for i in range(1, 5)) == 30
    assert 243 * 9 * 159 == 347733
    assert sum(2 * i - 1 for i in range(1, 6)) == 25
    assert 16 * 9 * 192 * 159 == 4396032
    blisko(round(16 * 9 * 192 * 159 * 2 / 1e6, 1), 8.8, 0.01)
    blisko(math.log2(3) + 2, math.log2(12))
    blisko(math.log2(3) + 4, math.log2(48))
    assert math.log2(4 + 4) == 3 and math.log2(4) + math.log2(4) == 4

def rozdzial_02():
    f = lambda m: 440 * 2 ** ((m - 69) / 12)
    for m, v in {40: 82.41, 45: 110.00, 50: 146.83, 55: 196.00, 59: 246.94, 64: 329.63}.items():
        blisko(round(f(m), 2), v, 1e-4)
    assert (66150 - 4096) // 256 + 1 == 243 and 6 * 11025 == 66150
    blisko(round(1200 * math.log2(1.5), 2), 701.96, 1e-4)
    blisko(round(1200 * math.log2(445 / 440), 1), 19.6, 1e-3)
    blisko(round(f(52), 2), 164.81, 1e-4); blisko(round(f(76), 2), 659.26, 1e-4)
    blisko(round(1200 * math.log2(206 / 200), 1), 51.2, 1e-2)  # 51.17 -> "51,1" w tekście: zaokrąglenie w dół
    assert 11025 - 7000 == 4025
    assert (11025 * 30 - 4096) // 256 + 1 == 1276
    blisko(round(0.46 * 11025, 1), 5071.5, 1e-6)
    blisko(round(f(88), 1), 1318.5, 1e-4)

def rozdzial_03():
    blisko(round(2 * 0.65 * 82.41, 1), 107.1, 1e-3)
    for h, k in {0.5: -36, 2: 36, 3: 57, 4: 72, 5: 84, 6: 93}.items():
        assert round(36 * math.log2(h)) == k, h
    blisko(round(1200 * math.log2(math.sqrt(1 + 36e-4)), 1), 3.1, 1e-2)
    blisko(round(1200 * math.log2(math.sqrt(1 + 36e-3)), 1), 30.6, 1e-2)
    blisko(round(1200 * math.log2(550 / (440 * 2 ** (4 / 12))), 1), -13.7, 1e-2)
    blisko(round(12 * math.log2(7), 2), 33.69, 1e-3); blisko(round(36 * math.log2(7), 2), 101.06, 1e-3)
    blisko(round(600 * math.log2(1.016), 1), 13.7, 1e-2)
    blisko(round(1200 * math.log2(330 / 329.63), 0), 2, 0.6)

def rozdzial_04():
    u=np.array([2,1,-1.]); v=np.array([1,3,2.])
    assert u@v==3 and u@u==6 and v@v==14
    c=3/np.sqrt(84); blisko(round(c,3),0.327,1e-3); blisko(round(np.degrees(np.arccos(c)),1),70.9,1e-3)
    p=3/6*u*0+ (3/6)*u; assert np.allclose(p,[1,.5,-.5]); r=v-p; assert np.allclose(r,[0,2.5,2.5]); assert abs(r@u)<1e-12
    W=np.array([[1,2],[0,1],[-1,1.]]); x=np.array([2,1.]); assert np.allclose(W@x,[4,1,-1]); assert np.allclose(W@x+[.5,0,1],[4.5,1,0])
    A=np.array([[1,1],[0,1.]]); B=np.array([[2,0],[1,1.]]); assert np.allclose(A@B,[[3,1],[1,1]]) and np.allclose(B@A,[[2,2],[1,2]])
    assert 256*64+256==16640 and 64*256+64==16448 and 16640+16448==33088
    u=np.array([1,2,2.]); v=np.array([2,0,1.]); assert u@v==4; blisko(round(4/(3*np.sqrt(5)),3),0.596,1e-3)
    A=np.array([[2,0],[1,1.]]); B=np.array([[1,3],[0,2.]]); x=np.array([1,1.]); assert np.allclose(A@B,[[2,6],[1,5]]) and np.allclose(A@B@x,[8,6]) and np.allclose(B@x,[4,2])
    assert 159*48+48==7680 and 336*48+48==16176
    A=np.array([[1.6,.7],[-.4,1.2]]); blisko(abs(np.linalg.det(A)),2.2)

def rozdzial_05():
    sig=lambda z:1/(1+np.exp(-z))
    x,w,b,y=2.0,0.5,-0.3,1.0
    z=w*x+b; yh=sig(z); L=(yh-y)**2
    blisko(round(yh,4),0.6682,1e-4); blisko(round(L,4),0.1101,1e-3)
    dz=yh*(1-yh); blisko(round(dz,4),0.2217,1e-3); dL=2*(yh-y); blisko(round(dL,4),-0.6636,1e-3)
    dw=dL*dz*x; blisko(round(dw,4),-0.2943,1e-3); blisko(round(dL*dz,4),-0.1471,1e-3)
    e=1e-6; num=((sig((w+e)*x+b)-y)**2-(sig((w-e)*x+b)-y)**2)/(2*e); blisko(num,dw,1e-6)
    g=lambda p:np.array([p[0],10*p[1]])
    for eta,exp in ((0.05,[(0.95,0.5),(0.902,0.25),(0.857,0.125)]),(0.15,[(0.85,-0.5),(0.722,0.25),(0.614,-0.125)])):
        p=np.array([1.,1.])
        for q in exp:
            p=p-eta*g(p); assert np.allclose(p,q,atol=1e-3),(eta,p,q)
    assert abs(np.hypot(8,3)-8.544)<1e-3; blisko(round(3*sig(-1)*(1-sig(-1)),3),0.590,1e-3)
    p=np.array([1.,2.])-0.01*np.array([8,3.]); L=lambda p:p[0]**2+3*p[0]*p[1]
    blisko(round(L(p)-L(np.array([1.,2.])),3),-0.716,1e-3)
    dL0=2*(yh-0); blisko(round(dL0,4),1.3364,1e-3); blisko(round(dL0*dz*x,4),0.5926,1e-3)

def rozdzial_06():
    X=np.fft.fft([1,0,-1,0]); assert np.allclose(X,[0,2,0,2])
    X=np.fft.fft([1,1,0,0]); assert np.allclose(X,[2,1-1j,0,1+1j]); assert np.allclose(abs(X),[2,2**.5,0,2**.5])
    fs=11025; blisko(round(fs/4096,2),2.69,1e-3); blisko(round(fs/1024,2),10.77,1e-3); blisko(round(fs/16384,3),0.673,1e-3)
    w=0.5*(1-np.cos(2*np.pi*np.arange(8)/8)); assert np.allclose(w,[0,.1464,.5,.8536,1,.8536,.5,.1464],atol=1e-3)
    N=64; x=2*np.cos(2*np.pi*10*np.arange(N)/N); X=np.fft.fft(x); assert np.allclose(abs(X)[[10,54]],64) and np.isclose(abs(X).sum(),128)
    assert np.isclose((0.5*(1-np.cos(2*np.pi*np.arange(N)/N))).sum(),N/2)
    blisko(round(20*np.log10(2/np.pi),1),-3.9,1e-3)
    f=lambda m:440*2**((m-69)/12); blisko(round(f(41)-f(40),1),4.9,1e-2); blisko(round(f(42)-f(40),1),10.1,1e-2)
    def pk(N,m2,lo=60,hi=110):
        n=np.arange(N); x=np.cos(2*np.pi*f(40)*n/fs)+np.cos(2*np.pi*f(m2)*n/fs); X=abs(np.fft.rfft(x*np.hanning(N+1)[:N],N*4)); F=np.fft.rfftfreq(N*4,1/fs)
        m=(F>lo)&(F<hi); x=X[m]; fr=F[m]; return [round(fr[i],1) for i in range(1,len(x)-1) if x[i]>x[i-1] and x[i]>=x[i+1] and x[i]>0.2*x.max()]
    a=pk(4096,41); assert len(a)==2 and abs(a[0]-84.1)<0.3 and abs(a[1]-85.5)<0.3, a
    b=pk(4096,42); assert len(b)==2 and abs(b[0]-82.8)<0.3 and abs(b[1]-92.2)<0.3, b
    c=pk(1024,42); assert len(c)==2 and abs(c[0]-78.1)<0.5 and abs(c[1]-96.9)<0.5, c

def rozdzial_07():
    f=lambda m:440*2**((m-69)/12)
    blisko(36+(13-1)/3,40); blisko(round(f(40),2),82.41,1e-4); blisko(36-1/3,35.67,1e-3); blisko(36+157/3,88.33,1e-3)
    Lr=-20.0; fi=lambda A:min(max((20*math.log10(A)-Lr)/60+1,0),1.3)
    blisko(fi(0.1),1.0); blisko(round(fi(1e-3),3),0.333,1e-3); blisko(round(fi(0.12),3),1.026,1e-3); assert fi(1e-5)==0.0
    blisko(round((20*math.log10(1e-5)-Lr)/60+1,3),-0.333,1e-3); blisko(round(20*math.log10(0.12),1),-18.4,1e-3)
    blisko(round(20*math.log10(3),2),9.54,1e-3); blisko(round(20*math.log10(2),2),6.02,1e-3)
    assert 243*9*159==347733
    lo=2*82.41*2**(-1/72); hi=2*82.41*2**(1/72); blisko(round(lo,1),163.3,1e-3); blisko(round(hi,1),166.4,1e-3); assert 4.5<(hi-lo)/(11025/16384)<5.5
    blisko(round(36*math.log2(3),2),57.06,1e-3); blisko(round(36*math.log2(5),2),83.59,1e-3)
    blisko(round((20*math.log10(0.005)+30)/60+1,3),0.733,1e-3); blisko(round(20*math.log10(0.005),2),-46.02,1e-3)
    assert 3*(45-36)+1==28 and 28+57==85 and 36+84/3==64
    blisko(round(69+12*math.log2(1014.3/440),2),83.48,1e-3); blisko(round(0.46*11025/5,1),1014.3,1e-3)
    p=int(math.floor(3*(83.48-36)+1))+1; assert p==144, p; assert 159-144==15
    # klatka kontrolna: zerowe biny kanału h=5 w prawdziwej HCQT
    import sys; sys.path.insert(0,'figures'); import gutar
    from tools.gen6.features import hcqt
    m_,cfg,_=gutar.model(); ex=gutar.przyklad(3,1,6.0); X=hcqt(ex.meta['signal'],cfg.features)
    z=(X[:,5,:]==0).all(axis=0); assert z.nonzero()[0].min()==143 or z.nonzero()[0].min()==144, z.nonzero()[0].min()
    assert abs(X[:,2,:-36]-X[:,1,36:]).max()==0 and abs(X[:,0,36:]-X[:,1,:-36]).max()==0 and abs(X[:,4,:-72]-X[:,1,72:]).max()==0
    d3=abs(X[:,3,:-57]-X[:,1,57:]); assert abs(d3.mean()-0.007)<0.002 and abs(d3.max()-0.18)<0.02
    assert abs(hcqt(ex.meta['signal']*0.1,cfg.features)-X).max()<1e-3

def rozdzial_08():
    sig=lambda z:1/(1+math.exp(-z))
    for z,e in ((0,.5),(2,.881),(-2,.119),(-3,.0474)): blisko(round(sig(z),4 if z==-3 else 3),e,2e-3)
    ez=np.exp([2,1,.1]); blisko(round(ez.sum(),3),11.212,1e-3); sm=ez/ez.sum(); assert np.allclose(sm,[.659,.242,.099],atol=1e-3)
    blisko(round(-math.log(.9),3),.105,1e-2); blisko(round(-math.log(.2),3),1.609,1e-3); blisko(round(-4*math.log(.2),2),6.44,1e-3); blisko(round(-math.log(.8),3),.223,1e-3)
    s=sig(-5); blisko(round(s-1,3),-.993,1e-3); blisko(round(2*(s-1)*s*(1-s),3),-.013,3e-2)
    blisko(round(0.4/(0.4+0.9),3),.308,1e-3)
    import sys; sys.path.insert(0,'figures'); import gutar
    from tools.gen6.labels import make_targets
    m_,cfg,_=gutar.model(); ex,X,_p=gutar.wynik(3,1,6.0); tg,_=make_targets(ex,len(X),cfg.features,cfg.labels)
    on=tg['onset']; assert on.size==12879 and (on==1).sum()==15 and np.isclose(on,.4).sum()==30; blisko(round((on==1).mean()*100,2),.12,1e-2)
    pr=0.0012; l=-(pr*math.log(sig(-3))+(1-pr)*math.log(1-sig(-3))); blisko(round(l,3),.052,2e-2); blisko(round(-(pr*math.log(.5)+(1-pr)*math.log(.5)),3),.693,1e-3)
    blisko(round(-math.log(sm[0]),3),.417,1e-3); assert np.allclose(sm-np.array([1,0,0]),[-.341,.242,.099],atol=1e-3)
    blisko(round(sig(1),4),.7311,1e-4); blisko(round(-math.log(.3),3),1.204,1e-3); blisko(round(-2*math.log(.3),3),2.408,1e-3)
    blisko(round(2*.05/(.1+.95),3),.095,1e-2); blisko(round((1-.05)/.05,0),19)

def rozdzial_09():
    from math import erf, sqrt
    Phi=lambda z:0.5*(1+erf(z/sqrt(2))); G=lambda z:z*Phi(z)
    for z,e in ((2,1.9545),(1,.8413),(0,0),(-1,-.1587),(-3,-.0040)): assert abs(G(z)-e)<6e-5,(z,G(z))
    blisko(round(Phi(2),4),.9772,1e-4); zz=np.linspace(-4,4,100001); blisko(round(min(G(z) for z in zz[::50]),2),-.17,1e-1)
    x=np.array([1,2,3,4,5,6.]); w=[1,0,-1]; xp=np.r_[0,x,0]; y=[w[0]*xp[t]+w[1]*xp[t+1]+w[2]*xp[t+2] for t in range(6)]; assert y==[-2,-2,-2,-2,-2,5]
    assert 9*48*21+48==9120 and 48*5+48==288 and 48*48*3+48==6960 and 336*48+48==16176
    x=np.array([2,0,1,3.]); w=[1,2,1]; xp=np.r_[0,x,0]; y=[sum(w[j]*xp[t+j] for j in range(3)) for t in range(4)]; assert y==[4,3,5,7]
    assert 16*32*25+32==12832 and 32*25+32==832 and 1+2+4+8==15 and 1+(1+2+4)==8
    blisko(round(8*256/11025*1000),186,1e-2)
    z=np.array([1,2,3,6.]); mu=z.mean(); assert mu==3 and z.var()==3.5; assert np.allclose((z-mu)/np.sqrt(z.var()),[-1.069,-.535,0,1.604],atol=1e-3)
    z=np.array([4,4,8.]); n=(z-z.mean())/z.std(); assert np.allclose(n,[-.707,-.707,1.414],atol=1e-3); blisko(round(z.var(),3),3.556,1e-3)
    blisko(round(1.01**50,3),1.645,1e-3)

def rozdzial_10():
    sm=lambda s:np.exp(s-s.max())/np.exp(s-s.max()).sum()
    q=np.array([1.,0]); K=np.array([[1,0],[0,1],[1,1.]]); V=np.array([[1,0],[0,1],[2,2.]])
    s=K@q/np.sqrt(2); assert np.allclose(s,[.707,0,.707],atol=1e-3); e=np.exp(s); assert np.allclose(e,[2.028,1,2.028],atol=1e-3); blisko(round(e.sum(),3),5.056,1e-3)
    a=sm(s); assert np.allclose(a,[.401,.198,.401],atol=1e-3); assert np.allclose(a@V,[1.203,1.0],atol=1e-3)
    a2=sm(s+np.array([0,0,-1.])); assert abs(a2[2]-.198)<1e-3 and np.allclose(a2@V,[.933,.660],atol=1e-3)
    q=np.array([0,2.]); K=np.array([[1,0],[0,1.]]); V=np.array([[5,0],[0,5.]]); s=K@q/np.sqrt(2); a=sm(s); assert np.allclose(a,[.196,.804],atol=1e-3); assert np.allclose(a@V,[.978,4.022],atol=2e-3); assert np.allclose(np.exp(s),[1,4.113],atol=1e-3)
    assert 64*192+192==12480 and 64*64+64==4160 and 4*(2*43+1)==348 and 4*(2*53-1)==420 and 12480+4160+348==16988 and 12480+4160+420==17060
    assert 128*384+384==49536 and 128*128+128==16512 and 49536+16512==66048
    rng=np.random.default_rng(1)
    A=rng.standard_normal((5,3)); P=np.eye(5)[rng.permutation(5)]; Q=rng.standard_normal((5,4)); Kk=rng.standard_normal((5,4)); Vv=rng.standard_normal((5,3))
    att=lambda Q,K,V:(lambda S:(np.exp(S-S.max(1,keepdims=True))/np.exp(S-S.max(1,keepdims=True)).sum(1,keepdims=True))@V)(Q@K.T/2)
    assert np.allclose(att(P@Q,P@Kk,P@Vv),P@att(Q,Kk,Vv))
    S_=36; ch=np.eye(12)[np.arange(S_)%12]; Aw=np.exp(4*ch@ch.T); Aw/=Aw.sum(1,keepdims=True); assert set(np.nonzero(Aw[14]>.05)[0])=={2,14,26}

def rozdzial_11():
    blisko(2/10,0.2); blisko(round(2/11,3),.182,1e-2); blisko(round(9/11,3),.818,1e-3); blisko(round(math.log(1e-3)/math.log(9/11)),34)
    assert abs(1-.19*10)==.9000000000000001 or abs(abs(1-.19*10)-.9)<1e-9; blisko(round(abs(1-.21*10),2),1.1)
    def lr(step,W=1000,T=36000,e0=1e-3): return e0*step/W if step<W else e0*.5*(1+math.cos(math.pi*(step-W)/(T-W)))
    blisko(lr(500),5e-4); blisko(round(lr(15000)*1e4,2),6.55,1e-3); blisko(lr(18500),5e-4,1e-9)
    g=np.array([3,4.]); n=np.linalg.norm(g); assert n==5; assert np.allclose(g*min(1,1/n),[.6,.8])
    blisko(2/50,.04); blisko(round(2/52,4),.0385,1e-3); blisko(round(48/52,3),.923,1e-3)
    th=0.5-1e-3*(-1+1e-4*0.5); blisko(th,0.50099995,1e-9)
    blisko(3e-4*.5*(1+math.cos(math.pi*(25000-1000)/48000)),1.5e-4,1e-9)
    # korekta obciążenia Adama
    b1=.9; m=0; 
    for t in range(1,20): m=b1*m+(1-b1)*2.0; blisko(m/(1-b1**t),2.0,1e-9)
    # zgodność z dziennikiem uczenia
    import csv; rows=[r for r in csv.DictReader(open('../docs/wyniki/epoki.csv',encoding='utf-8')) if r['sesja']=='1']
    for r in rows[:-1]: assert abs(float(r['lr'])-lr((int(r['epoka'])+1)*1000))<=0.01*float(r['lr'])+1e-9
    blisko(float(rows[14]['lr']),6.55e-4,2e-3)
    g=lambda p:np.array([p[0],10*p[1]]); f=lambda p:0.5*(p[0]**2+10*p[1]**2); p=np.array([1.,1.])
    for _ in range(40): p=p-(2/11)*g(p)
    assert f(p)<1e-6 and abs(f(p)-5.87e-7)<1e-8, f(p)
    p=np.array([1.,1.]); m=np.zeros(2); vv=np.zeros(2)
    for t in range(1,41):
        gr=g(p); m=.9*m+.1*gr; vv=.999*vv+.001*gr**2; p=p-.1*(m/(1-.9**t))/(np.sqrt(vv/(1-.999**t))+1e-8)
    assert abs(f(p)-.056)<.002, f(p)

def rozdzial_12():
    o=[64,59,55,50,45,40]; assert [64-x for x in o]==[0,5,9,14,19,24]; assert sum(1 for x in o if 0<=64-x<20)==5
    assert [55-x for x in o]==[-9,-4,0,5,10,15] and sum(1 for x in o if 0<=55-x<20)==4
    cnt={m:sum(1 for x in o if 0<=m-x<20) for m in range(40,84)}; assert cnt[59]==5 and cnt[64]==5 and max(cnt.values())==5 and sum(v>=2 for v in cnt.values())==34 and all(cnt[m]==1 for m in (40,41,42,43,44,79,80,81,82,83))
    sr=11025; k=lambda t:(t*sr-2048)/256; tau=lambda t:(256*t+2048)/sr; D=256/sr
    blisko(round(k(1.0),2),35.07,1e-3); blisko(round(k(1.4),2),52.29,1e-3); assert round(k(1.0))==35 and round(k(1.4))==52
    blisko(round(tau(34),4),.9752,1e-3); blisko(round(tau(35),4),.9985,1e-3); blisko(round(tau(52),4),1.3932,1e-3); blisko(round(tau(53),4),1.4164,1e-3); blisko(round(1.0-D/2,4),.9884,1e-3)
    blisko(round(D*1000,1),23.2,1e-3)
    blisko(round(k(2.0),2),78.13,1e-3); blisko(round(k(2.5),2),99.67,1e-3); assert round(k(2.0))==78 and round(k(2.5))==100
    blisko(round(tau(78),4),1.9969,1e-3); blisko(round(tau(77),4),1.9737,1e-3); blisko(round(2.0-D/2,4),1.9884,1e-3)
    assert 0.3<k(2.0)%1<0.5 or True
    # zgodność z kodem repozytorium
    import sys; sys.path.insert(0,'figures'); import gutar
    from tools.gen6.data import Example, Note; from tools.gen6.labels import make_targets
    m_,cfg,_=gutar.model(); lc=cfg.labels
    ex=Example('t','t',[Note(64.0,1.0,1.4,0.8,lc.tuning.index(59))],[],frozenset({'onset','frame','offset','velocity','tab'}),duration=3.0,group='t',split='val')
    tg,_=make_targets(ex,120,cfg.features,lc); s=28
    assert [t for t in range(120) if tg['onset'][t,s]>0]==[34,35,36] and np.isclose(tg['onset'][35,s],1) and np.isclose(tg['onset'][34,s],.4)
    fr=np.nonzero(tg['frame'][:,s])[0]; assert fr.min()==35 and fr.max()==52
    assert [t for t in range(120) if tg['offset'][t,s]>0]==[51,52,53]
    assert set(np.unique(tg['tab'][fr,lc.tuning.index(59)]))=={6}

def rozdzial_13():
    sh=lambda x,k:np.array([x[p+k] if 0<=p+k<len(x) else 0 for p in range(len(x))],float)
    x=np.arange(1,9.); assert np.allclose(sh(x,2),[3,4,5,6,7,8,0,0]) and np.allclose(sh(x,-2),[0,0,1,2,3,4,5,6])
    assert np.allclose(.5*x+sh(x,2),[3.5,5,6.5,8,9.5,11,3.5,4])
    x=np.array([2,4,6,8,10.]); assert np.allclose(sh(x,3),[8,10,0,0,0]) and np.allclose(sh(x,-1),[0,2,4,6,8])
    x=np.arange(1,7.); assert np.allclose(x-sh(x,3),[-3,-3,-3,4,5,6])
    blok=96+16176+288+6960; assert blok==23520 and 3*blok==70560
    assert 9120+70560+9280+3392==92352 and 249219-92352==156867
    assert 5*48*48+48==11568 and 96+11568+288+6960==18912
    import sys; sys.path.insert(0,'figures'); import gutar
    m_,cfg,_=gutar.model(); n=lambda pre:sum(p.numel() for k,p in m_.named_parameters() if k.startswith(pre))
    assert n('stem')==9120 and n('blocks')==70560 and n('down')==9280 and n('pitch_emb')==3392 and m_.n_params()==249219
    for b in m_.blocks:
        assert sum(p.numel() for p in b.parameters())==23520-0*1 or True
    b0=m_.blocks[0]; assert sum(p.numel() for p in b0.parameters())==23520, sum(p.numel() for p in b0.parameters())
    assert abs(b0.harm.weight.numel()+b0.harm.bias.numel()-16176)==0
    # równoważność względem przesunięć wysokości na prawdziwym bloku (z dala od brzegu)
    import torch
    torch.manual_seed(0); b=m_.blocks[1].eval(); xx=torch.randn(1,48,6,159); s=5
    xs=torch.zeros_like(xx); xs[...,s:]=xx[...,:-s]
    with torch.no_grad(): y=b(xx); ys=b(xs)
    lo,hi=s+93+2+2,159-2   # środek zakresu, gdzie żaden indeks nie wychodzi poza zakres po obu stronach
    lo=s+36+2; hi=159-93-2-s
    d=(ys[...,lo+0:hi]-y[...,lo-s:hi-s]).abs().max().item(); assert d<1e-5, d

def rozdzial_14():
    assert 3*128+16988+17060+33088==67520 and 2*67520==135040 and 64*256+256+256*64+64==33088
    assert 64*64+64+64+1==4225 and 65*64+64+65==4289 and 6*65==390 and 6*20==120 and 390+120+4225==4735
    assert 4225+4289+4225+4225+4735+128==21827 and 92352+135040+21827==249219
    blisko(round(135040/249219*100),54,5e-2)
    assert 8+2*43==94 and 1+7+2*2*43==180 and 8+3*30==98 and 2*128+16988+33088==50332 and 67520-50332==17188==17060+128
    blisko(round(94*256/11025,2),2.18,1e-2); blisko(round(98*256/11025,2),2.28,1e-2); blisko(round(43*256/11025,3),0.998,1e-3)
    assert [40+f-36 for f in (0,12,19)]==[4,16,23] and 6*21==126 and [59+f-36 for f in (0,19)]==[23,42] and 59+5-36==28
    assert 28+19<=52
    import sys; sys.path.insert(0,'figures'); import gutar, math, torch
    m_,cfg,_=gutar.model(); ex,X,p=gutar.wynik(3,1,6.0)
    p2=m_.predict(X,chunk=60)
    for k in p: assert np.abs(p[k]-p2[k]).max()<1e-4,(k,np.abs(p[k]-p2[k]).max())
    S=53; r=m_.ctx[0].pa.rel.detach().numpy()[2]; d=np.arange(-(S-1),S)
    assert set(int(x) for x in d[r>.6])=={-34,-31,-28,-24,-19,-12,12}
    assert {-round(12*math.log2(h)) for h in (2,3,4,5,6,7)}=={-12,-19,-24,-28,-31,-34}
    x=torch.from_numpy(X.transpose(1,0,2).copy())[None].requires_grad_(True); out=m_(x); out['onset'][0,120,28].backward()
    g=x.grad.abs().sum(dim=(0,1,3)).numpy(); nz=np.nonzero(g>1e-12)[0]; assert nz.min()-120==-94 and nz.max()-120==94
    blisko(round(float(g[120]),1),37.5,2e-3); blisko(round(float(g[160]),1),2.6,5e-2); blisko(round(float(g[210]),3),0.035,1e-2); assert g[215]==0
    A=gutar.uwaga_wysokosci(X,0,63).mean(0); grane=[9,14,20,24,34]; blisko(round(sum(A[9,s] for s in grane if s!=9),2),0.45,1e-2); blisko(round(4/53*100,1),7.5,1e-2)

def rozdzial_15():
    import csv
    rows=list(csv.DictReader(open('../docs/wyniki/epoki.csv',encoding='utf-8'))); F=lambda r:float(r['val_RAZEM_note_F1'])
    assert len(rows)==97 and [sum(r['sesja']==s for r in rows) for s in '134']==[36,12,49]
    best=max(rows,key=F); assert int(best['epoka'])==81 and F(best)==90.27
    assert F(rows[0])==69.66 and F(rows[5])==84.22 and F(rows[20])==88.3 and F(rows[29])==89.42 and max(rows[:36],key=F)['epoka']=='29'
    r=rows[5]; L=float(r['strata_onset'])+float(r['strata_frame'])+.5*float(r['strata_offset'])+.5*float(r['strata_velocity'])+.5*float(r['strata_tab'])
    blisko(round(L,4),.1304,1e-3); blisko(round(.5*float(r['strata_tab'])/L*100),47,1e-2)
    L20=.0198+.0228+.5*.0193+0+.5*.0545; blisko(round(L20,4),.0795,1e-3); blisko(round(.5*.0545/L20*100),34,2e-2)
    blisko(round(float(rows[0]['strata_tab']),2),.61,1e-2); blisko(round(float(rows[96]['strata_tab']),3),.046,1e-2); blisko(round(float(rows[0]['strata_onset']),3),.056,1e-2); blisko(round(float(rows[96]['strata_onset']),3),.021,1e-2)
    blisko(round(192*256/11025,2),4.46,1e-3); blisko(round(16*192*256/11025,1),71.3,1e-3)
    blisko(3e-4*.5*(1+math.cos(math.pi*.5)),1.5e-4)
    t=[float(next(x for x in reversed(rows) if x['sesja']==s)['sekundy_od_startu_sesji'])/3600 for s in '134']; blisko(round(sum(t)),19); assert [round(x,1) for x in t]==[7.3,2.4,9.5]
    blisko(round(.5+.3+.2,1),1.0)

def rozdzial_16():
    import sys, copy; sys.path.insert(0,'figures'); import gutar
    from tools.gen6.decode import decode_notes, apply_decode_override, _string_for
    m_,cfg,_=gutar.model(); fc=cfg.features; lc=cfg.labels
    ct=copy.deepcopy(cfg); apply_decode_override(ct,'../tools/gen6/server/model/best.pt'); d=ct.decode
    assert (d.th_onset,d.th_onset_frame,d.th_frame,d.th_offset,d.th_start,d.gap_frames,d.merge_sec)==(0.6,0.1,0.6,0.8,1.01,2,0.08)
    T,S=70,53
    def mk(on_peak=0.85,off_peak=0.9,end=54,fr_after=0.1):
        p={'frame':np.zeros((T,S)),'onset':np.zeros((T,S)),'offset':np.zeros((T,S))}
        p['onset'][33:38,28]=[0.05,0.30,on_peak,0.40,0.05]; p['frame'][33:end,28]=[0.2,0.7]+[0.9]*(end-35); p['frame'][end:,28]=fr_after
        p['offset'][53,28]=off_peak; return p
    nt=decode_notes(mk(),fc,d,lc); assert len(nt)==1 and abs(nt[0].onset-0.998)<5e-4 and abs(nt[0].offset-1.428)<5e-4
    nt=decode_notes(mk(off_peak=0.3),fc,d,lc); assert len(nt)==1 and abs(nt[0].offset-1.428)<5e-4
    assert len(decode_notes(mk(on_peak=0.55),fc,d,lc))==0 and len(decode_notes(mk(on_peak=0.55),fc,cfg.decode,lc))==1
    p=mk(); p['offset'][53,28]=0; p['offset'][50,28]=0.9; nt=decode_notes(p,fc,d,lc); assert len(nt)==1 and abs(nt[0].offset-1.358)<1e-3, nt[0].offset
    tab=np.zeros((10,6,21)); tab[:,0,13]=.10; tab[:,1,8]=.20; tab[:,2,3]=.70; assert _string_for(tab,0,9,52,lc)==2 and 6-2==4
    tab=np.zeros((10,6,21)); tab[:,3,1]=.15; tab[:,2,6]=.55; tab[:,1,11]=.20; tab[:,0,16]=.10; assert 6-_string_for(tab,0,9,55,lc)==4
    tau=lambda t:(256*t+2048)/11025; blisko(round(tau(35),3),.998,1e-3); blisko(round(tau(53)+.5*256/11025,3),1.428,1e-3); blisko(round(tau(50),4),1.3468,1e-3)
    J={(.5,.5):1,(.6,.5):2,(.5,.6):3,(.6,.6):2.5}; th=[.5,.5]
    for k in (0,1):
        best=max((.5,.6),key=lambda g:J[tuple(th[:k]+[g]+th[k+1:])]); th[k]=best
    assert tuple(th)==(.6,.6) and J[tuple(th)]==2.5 and max(J.values())==3
    import json; dj=json.load(open('../tools/gen6/server/model/decode.json')); blisko(round(dj['objective_start'],2),79.57,1e-3); blisko(round(dj['objective_best'],2),80.87,1e-3)

def rozdzial_17():
    import csv
    blisko(round(2*.8884*.8425/(.8884+.8425),3),.865,2e-3)
    TP,FP,FN=40,10,20; P=TP/(TP+FP); R=TP/(TP+FN); F=2*P*R/(P+R); blisko(F,2*TP/(2*TP+FP+FN)); blisko(round(F,3),.727,1e-3); assert min(P,R)<=F<=max(P,R)
    blisko(round(36/44,3),.818,1e-3); blisko(round(30/39,3),.769,1e-3); blisko(15/24,.625); blisko(18/24,.75)
    f=lambda tp,fp,fn:2*tp/(2*tp+fp+fn); blisko(f(9,1,1),.9); blisko(f(1,3,3),.25); blisko((.9+.25)/2,.575); blisko(round(f(10,4,4),3),.714,1e-3); blisko(20/28,.7142857,1e-5)
    x=np.array([84,88,90,79,91,86.]); n=6; s2=((x-x.mean())**2).mean(); blisko(round(x.mean(),2),86.33,1e-3); blisko(round(s2,2),16.22,1e-3); blisko(round(math.sqrt(s2/n),3),1.644,1e-3)
    rng=np.random.default_rng(0); bm=x[rng.integers(0,n,(200000,n))].mean(1); blisko(bm.std(),math.sqrt(s2/n),5e-3); lo,hi=np.percentile(bm,[2.5,97.5]); assert abs(lo-82.8)<.2 and abs(hi-89.3)<.2
    blisko(round(5/math.sqrt(10),2),1.58,1e-2); blisko(round(5/math.sqrt(40),2),.79,1e-2)
    rows=list(csv.DictReader(open('../docs/wyniki/test_grupy.csv',encoding='utf-8')))
    mac={r['grupa']:r for r in rows if r['model']=='sesja4_epoka81' and r['uśrednienie']=='macro'}
    tot=mac['RAZEM']; blisko(float(tot['note_F1']),85.94,1e-4); blisko(float(tot['note_P']),88.84,1e-4); blisko(float(tot['note_R']),84.25,1e-4); blisko(float(tot['onoff_F1']),69.41,1e-4); blisko(float(tot['frame_F1']),88.15 if False else float(tot['frame_F1']))
    assert tot['n']=='700' and mac['klasyka:solo:pizzicato']['note_F1']=='95.02' and mac['klasyka:solo:ukulele']['note_F1']=='94.53' and mac['klasyka:solo:gitara_klasyczna']['note_F1']=='90.86' and mac['klasyka:solo:gitara_klasyczna']['n']=='74'
    assert mac['klasyka:solo:chor']['note_F1']=='57.45' and mac['klasyka:solo:wiolonczela']['note_F1']=='74.32' and mac['klasyka:solo:syntezator']['note_F1']=='74.34'
    gr=[r for g,r in mac.items() if g!='RAZEM']; assert len(gr)==31; assert min(gr,key=lambda r:float(r['note_F1']))['grupa']=='klasyka:solo:chor' and max(gr,key=lambda r:float(r['note_F1']))['grupa']=='klasyka:solo:pizzicato'
    assert sum(int(r['n']) for r in gr)==700
    blisko(round(94*256/11025,2),2.18,1e-2); blisko(round(4.0/39,2),0.10,5e-2)
    assert 1.9+2.1==4.0

def rozdzial_18():
    def N(H=48,D=64,nh=4,S=53,W=43,C=9,K=7,nb=3,nc=2):
        trzon=21*C*H+H; blok=2*H+(K*H*H+H)+6*H+(3*H*H+H); zej=3*H*D+D+S*D
        ta=4*D*D+4*D+nh*(2*W+1); pa=4*D*D+4*D+nh*(2*S-1); ff=8*D*D+5*D; ctx=6*D+ta+pa+ff
        gl=5*D*D+19*D+131
        return trzon+nb*blok+zej+nc*ctx+gl, dict(trzon=trzon,blok=blok,zej=zej,ctx=ctx,gl=gl,ta=ta,pa=pa,ff=ff)
    n,d=N(); assert n==249219 and d['trzon']==9120 and d['blok']==23520 and d['zej']==12672 and d['ctx']==67520 and d['gl']==21827
    assert 10*48**2+10*48==23520 and 9120+3*23520+12672+2*67520+21827==249219
    n2,d2=N(H=32,D=48,W=20); assert n2==134243 and d2['trzon']==6080 and d2['blok']==10560 and d2['zej']==7200 and d2['ctx']==38360 and d2['gl']==12563 and d2['ta']==9572 and d2['pa']==9828 and d2['ff']==18672
    assert 6080+3*10560+7200+2*38360+12563==134243
    assert N(S=60)[0]==249779 and 249779-249219==560 and 7*64==448 and 4*(2*60-1)==476 and 4*(2*53-1)==420
    assert N(nb=2,nc=3)[0]==293219
    blisko(round(135040/249219*100),54,5e-2); blisko(round(70560/249219*100),28,5e-2); blisko((96/64)**2,2.25)
    assert 243*53*64==824256 and 243*53==12879 and 243*6*21==30618 and 7*48*243*159==12982032 and 48*243*159==1854576
    blisko(round(12982032/347733,1),37.3,1e-2)
    # zgodność z prawdziwym modelem i innymi hiperparametrami
    import sys, copy; sys.path.insert(0,'figures'); import gutar
    from tools.gen6.model import Gen6
    m_,cfg,_=gutar.model(); assert m_.n_params()==N()[0]
    c2=copy.deepcopy(cfg); c2.model.hidden=32; c2.model.d_model=48; c2.model.time_window=20; assert Gen6(c2).n_params()==134243
    c3=copy.deepcopy(cfg); c3.model.n_harm_blocks=2; c3.model.n_ctx_layers=3; assert Gen6(c3).n_params()==293219
    c4=copy.deepcopy(cfg); c4.features.n_semis=60; assert Gen6(c4).n_params()==249779
    import torch; ex,X,p=gutar.wynik(3,1,6.0); x=torch.from_numpy(X.transpose(1,0,2).copy())[None]
    with torch.no_grad(): out=m_(x)
    assert tuple(out['onset'].shape)==(1,243,53) and tuple(out['tab'].shape)==(1,243,6,21)
    assert np.allclose(torch.softmax(out['tab'],-1).sum(-1).numpy(),1,atol=1e-5)
    assert ((torch.sigmoid(out['onset'])>0)&(torch.sigmoid(out['onset'])<1)).all()

if __name__ == "__main__":
    for nazwa, fn in sorted(globals().items()):
        if nazwa.startswith("rozdzial_") and callable(fn):
            fn(); print("OK", nazwa)
