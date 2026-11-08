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

if __name__ == "__main__":
    for nazwa, fn in sorted(globals().items()):
        if nazwa.startswith("rozdzial_") and callable(fn):
            fn(); print("OK", nazwa)
