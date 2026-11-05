"""Rysunki do docs/PRACA_NAUKOWA.md (python3 tools/make_figures_paper.py). Wymaga numpy, matplotlib; HCQT z tools/gen6/features.py."""
import os, sys, csv, math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, 'docs', 'rysunki')
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({'font.size': 9, 'axes.grid': True, 'grid.alpha': .25, 'axes.spines.top': False, 'axes.spines.right': False,
                     'figure.dpi': 100, 'savefig.dpi': 200, 'savefig.bbox': 'tight'})
B, O, G, R, K = '#1f6fb4', '#e08a1e', '#2a9d5c', '#c8382c', '#444444'
f = lambda m: 440 * 2 ** ((np.asarray(m, float) - 69) / 12)
def save(name): plt.savefig(os.path.join(OUT, name + '.png')); plt.close()

# 1. skala logarytmiczna, struny
fig, ax = plt.subplots(1, 2, figsize=(8, 3))
m = np.linspace(36, 88, 300)
ax[0].plot(m, f(m), color=B)
for i, s in enumerate((40, 45, 50, 55, 59, 64)):
    ax[0].plot(s, f(s), 'o', color=O); ax[0].annotate('%.0f Hz' % f(s), (s, f(s)), (s - 1, f(s) + 90), fontsize=7)
ax[0].set(xlabel='nuta MIDI $m$', ylabel='częstotliwość [Hz]', title='skala liniowa: odstępy rosną')
ax[1].semilogy(m, f(m), color=B)
for s in (40, 45, 50, 55, 59, 64): ax[1].plot(s, f(s), 'o', color=O)
ax[1].set(xlabel='nuta MIDI $m$', title='skala log: półtony są równe (pomarańczowe = struny)')
save('r01_skala')

# 2. alikwoty na osi log
fig, ax = plt.subplots(2, 1, figsize=(8, 4.2), sharex=True)
for a, m0, c in ((ax[0], 40, B), (ax[1], 45, G)):
    f0 = f(m0)
    for h in range(1, 7):
        a.vlines(36 * math.log2(h) / 36 * 12 + m0, 0, 1 / h ** .7, color=c, lw=3)
        a.text(m0 + 12 * math.log2(h), 1 / h ** .7 + .05, '%d×' % h, ha='center', fontsize=8)
    a.set_ylim(0, 1.3); a.set_ylabel('energia'); a.set_title('nuta MIDI %d (%.1f Hz): alikwoty $h f_0$' % (m0, f0), fontsize=9)
ax[1].set_xlabel('oś logarytmiczna (półtony); układ alikwotów: 0, +12, +19, +24, +28, +31 półtonów, tak samo dla każdej nuty')
save('r02_alikwoty')

# 3. okno Hanna i rozdzielczość
fs = 11025
fig, ax = plt.subplots(1, 3, figsize=(9, 2.8))
n = np.arange(64); ax[0].plot(n, .5 * (1 - np.cos(2 * np.pi * n / 64)), color=B); ax[0].plot(n, np.ones(64), '--', color=K, lw=.8)
ax[0].set(title='okno Hanna vs prostokątne', xlabel='próbka $n$')
t0 = np.arange(8192) / fs
sig = np.sin(2 * np.pi * f(40) * t0) + np.sin(2 * np.pi * f(41) * t0)
for a, N, c in ((ax[1], 1024, R), (ax[2], 4096, G)):
    x = sig[:N] * (.5 * (1 - np.cos(2 * np.pi * np.arange(N) / N)))
    X = np.abs(np.fft.rfft(x, 4 * N)) * 4 / N; fr = np.arange(len(X)) * fs / (4 * N)
    a.plot(fr, X, color=c); a.set_xlim(60, 110)
    a.axvline(f(40), color=K, ls=':'); a.axvline(f(41), color=K, ls=':')
    a.set(title='$N=%d$ (%.0f ms): %s' % (N, 1000 * N / fs, 'zlane piki' if N == 1024 else 'dwa piki'), xlabel='Hz')
ax[1].text(62, .1, 'E2 i F2 (82,4 i 87,3 Hz)', fontsize=7)
save('r03_okno')

# 4. prawdziwe HCQT z syntetycznej gitary
from tools.gen6.features import hcqt
from tools.gen6.config import FeatureConfig
cfg = FeatureConfig()
def pluck(m, t0, dur, tot, amp=1.0):
    t = np.arange(int(tot * fs)) / fs; y = np.zeros_like(t); f0 = f(m)
    env = np.exp(-(t - t0) * 3.0) * (t >= t0) * (t < t0 + dur)
    for h in range(1, 12):
        if h * f0 < fs / 2 * .9: y += env * amp / h ** 1.1 * np.sin(2 * np.pi * h * f0 * t * (1 + 1e-4 * h * h))
    return y
tot = 3.0
sig = pluck(40, .2, 1.2, tot) + pluck(52, 1.0, 1.0, tot) + pluck(55, 1.0, 1.0, tot) + pluck(59, 1.0, 1.0, tot)
sig += .003 * np.random.default_rng(0).standard_normal(len(sig))
X = hcqt(sig.astype(np.float32), cfg)
names = ['długie, $h=0{,}5$', 'długie, $h=1$', 'długie, $h=2$', 'krótkie, $h=1$']
idx = [0, 1, 2, 6]
fig, ax = plt.subplots(1, 4, figsize=(10, 3.4), sharey=True)
ext = [0, X.shape[0] * 256 / fs, 36 - 1 / 3, 36 + (158 - 1) / 3]
for a, i, nm in zip(ax, idx, names):
    a.imshow(X[:, i].T, origin='lower', aspect='auto', extent=ext, cmap='magma', vmin=0, vmax=1.2); a.set_title(nm, fontsize=8); a.set_xlabel('czas [s]'); a.grid(False)
ax[0].set_ylabel('bin $p$ jako wysokość MIDI $m(p)$')
save('r04_hcqt')

# 5. blok harmoniczny: przesunięcia; dylatacja
fig, ax = plt.subplots(1, 2, figsize=(9, 3))
ks = [-36, 0, 36, 57, 72, 84, 93]; p0 = 100
ax[0].bar(range(160), np.exp(-((np.arange(160) - p0 - 0) ** 2) / 2) * 0, color='none')
ax[0].axhline(0, color=K, lw=.6)
for k in ks:
    ax[0].annotate('', (p0 + k, 0), (p0 + k, 1), arrowprops=dict(arrowstyle='-|>', color=O))
    ax[0].text(p0 + k, 1.05 + (.12 if k in (84,) else 0), '%+d' % k if k else '0', ha='center', fontsize=7)
ax[0].plot([p0], [0], 'o', color=R); ax[0].text(p0, -.22, 'bin $p$\n(kandydat $f_0$)', ha='center', fontsize=7, color=R)
ax[0].set_xlim(55, 215); ax[0].set_ylim(-.4, 1.3); ax[0].set_yticks([]); ax[0].set_xlabel('bin (co 1/3 półtonu)')
ax[0].set_title('blok harmoniczny: z binu $p$ czytamy 7 miejsc', fontsize=9)
for d, y, c in ((1, 0, B), (2, 1, G), (4, 2, O)):
    ts = [-d, 0, d]; ax[1].scatter(ts, [y] * 3, s=60, color=c, zorder=3); ax[1].text(5.5, y, '$d=%d$' % d, va='center')
    ax[1].plot([-4.5, 4.5], [y, y], color='#ccc', lw=.6, zorder=1)
ax[1].set(xlim=(-5, 7), ylim=(-.6, 2.6), xlabel='przesunięcie w klatkach względem $t$', yticks=[], title='filtr $3\\times1$ z dylatacją: ±1, ±2, ±4 klatki')
save('r05_blok')

# 6. architektura
fig, ax = plt.subplots(figsize=(10, 3.6)); ax.axis('off'); ax.set_xlim(0, 100); ax.set_ylim(0, 36)
def box(x, y, w, h, t, c, fs_=7):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.2', fc=c, ec=K, lw=.8)); ax.text(x + w / 2, y + h / 2, t, ha='center', va='center', fontsize=fs_)
bl = [('HCQT\n9×T×159', '#e8f0fa'), ('trzon\nconv 3×7\n48 kan.', '#d9e8f7'), ('3× blok\nharmoniczny\n(48 kan.)', '#cfe3f5'), ('zejście ×3\n+ osadzenie\nwysokości\nT×53×64', '#f7e6cc'), ('2× kontekst:\nuwaga w czasie\n+ uwaga\nmiędzy wys.\n+ FF', '#fbd9b0'), ('LN', '#eee')]
x = 1
for t, c in bl:
    box(x, 14, 11, 12, t, c, 6.5)
    if x > 1: ax.annotate('', (x, 20), (x - 1.8, 20), arrowprops=dict(arrowstyle='-|>', color=K))
    x += 13
hs = [('początek', 31), ('brzmi (+$p_{on}$)', 25), ('koniec', 19), ('głośność', 13), ('tabulatura\n6×21', 6)]
for t, y in hs:
    box(82, y - 3, 16, 5, t, '#dff2e5'); ax.annotate('', (81.7, y - .5), (79, 20), arrowprops=dict(arrowstyle='-|>', color=K, lw=.6))
ax.text(1, 31, '$\\sum$ parametrów: 249 219', fontsize=8); ax.text(1, 9, 'wejście $[B,9,T,159]\\to[B,48,T,159]\\to[B,T,53,64]\\to$ mapy $[B,T,53]$', fontsize=8)
save('r06_architektura')

# 7. uwaga: maski i premia
fig, ax = plt.subplots(1, 4, figsize=(11, 2.8))
T = 30; W = 8; i, j = np.meshgrid(range(T), range(T), indexing='ij')
ax[0].imshow((abs(i - j) <= W), cmap='Blues', origin='upper'); ax[0].set_title('okno $\\pm W$ (dwukierunkowe)', fontsize=8)
ax[1].imshow(((abs(i - j) <= W) & (j <= i)), cmap='Blues', origin='upper'); ax[1].set_title('przyczynowe ($j\\leq i$)', fontsize=8)
for a in ax[:2]: a.set(xlabel='klucz $j$ (klatka)', ylabel='zapytanie $i$'); a.grid(False)
d = np.arange(-24, 25); r = np.zeros_like(d, float)
for k, v in ((12, 1.0), (19, .8), (24, .7), (-12, 1.0), (-19, .8), (-24, .7), (0, .2)): r[d == k] = v
ax[2].bar(d, r, color=O); ax[2].set(title='ILUSTRACJA premii $r_{j-i}$\n(pików nie zmierzono)', xlabel='$j-i$ [półtony]', xticks=[-24, -12, 0, 12, 24]); ax[2].title.set_fontsize(8)
q = np.array([1, 0.]); Kk = np.array([[1, 0], [0, 1], [1, 1.]]); s = Kk @ q / math.sqrt(2); a_ = np.exp(s) / np.exp(s).sum()
ax[3].bar(['$k_1$', '$k_2$', '$k_3$'], a_, color=[B, B, B]); ax[3].set_title('przykład z M9: wagi $a_{ij}$ = 0,40 / 0,20 / 0,40', fontsize=8)
for xx, v in enumerate(a_): ax[3].text(xx, v + .01, '%.3f' % v, ha='center', fontsize=8)
save('r07_uwaga')

# 8. aktywacje i BCE
fig, ax = plt.subplots(1, 3, figsize=(10, 2.8))
z = np.linspace(-6, 6, 300); ax[0].plot(z, 1 / (1 + np.exp(-z)), color=B, label='sigmoid'); ax[0].set(title='sigmoid: logit $\\to$ prawdopodobieństwo', xlabel='$z$'); ax[0].axhline(.5, color=K, lw=.5)
from math import erf
zz = np.linspace(-4, 4, 300); gl = zz * .5 * (1 + np.array([erf(v / math.sqrt(2)) for v in zz]))
ax[1].plot(zz, gl, color=G, label='GELU'); ax[1].plot(zz, np.maximum(zz, 0), '--', color=K, lw=.8, label='ReLU'); ax[1].legend(); ax[1].set(title='GELU i ReLU', xlabel='$z$')
p = np.linspace(.01, .99, 200)
for al, c in ((1, B), (4, R)): ax[2].plot(p, -al * np.log(p), color=c, label='$\\alpha=%d$' % al)
ax[2].plot(p, -np.log(1 - p), color=G, label='$y=0$'); ax[2].set(ylim=(0, 6), title='BCE: kara dla $y=1$ (i $y=0$)', xlabel='przewidziane $p$'); ax[2].legend()
save('r08_funkcje')

# 9. etykiety jednej nuty
fig, ax = plt.subplots(figsize=(8, 2.6)); tt = np.arange(40)
on = np.zeros(40); on[10] = 1; on[9] = on[11] = .4
fr = ((tt >= 9.5) & (tt <= 30)).astype(float); off = np.zeros(40); off[30] = 1; off[29] = off[31] = .4
ax.step(tt, fr, where='mid', color=G, label='brzmi $y_{fr}$'); ax.bar(tt, on, color=B, label='początek $y_{on}$ (1 i 0,4)'); ax.bar(tt, off, color=R, label='koniec $y_{off}$')
ax.set(xlabel='klatka $t$ (1 klatka = 23,2 ms)', ylim=(0, 1.35), title='mapy celów dla jednej nuty (jeden półton $s$)'); ax.legend(ncol=3, fontsize=7, loc='upper center')
save('r09_etykiety')

# 10. dekoder
rng = np.random.default_rng(3); tt = np.arange(60)
pon = .02 + 0 * tt; pon = pon + .9 * np.exp(-((tt - 12) ** 2) / 1.5) + .75 * np.exp(-((tt - 40) ** 2) / 1.5)
pfr = .03 + .9 / (1 + np.exp(-(tt - 11))) * (tt < 30) + .85 / (1 + np.exp(-(tt - 39))) * (tt < 55)
pfr[28:33] = np.minimum(pfr[28:33], [.8, .55, .3, .1, .05]); pfr[53:58] = [.7, .5, .2, .08, .04]
pfr = np.clip(pfr, 0, 1); poff = .02 + .85 * np.exp(-((tt - 30) ** 2) / 1.5) + .3 * np.exp(-((tt - 54) ** 2) / 4)
fig, ax = plt.subplots(figsize=(8, 3)); ax.plot(tt, pon, color=B, label='$p_{on}$'); ax.plot(tt, pfr, color=G, label='$p_{fr}$'); ax.plot(tt, poff, color=R, label='$p_{off}$')
ax.axhline(.6, color=B, ls=':', lw=.8); ax.axhline(.6, color=G, ls='--', lw=.5); ax.axhline(.8, color=R, ls=':', lw=.8)
ax.text(0.5, .63, '$\\theta_{on}=\\theta_{fr}=0{,}6$', fontsize=7); ax.text(0.5, .83, '$\\theta_{off}=0{,}8$', fontsize=7, color=R)
ax.add_patch(Rectangle((12, 1.02), 18, .05, color=O)); ax.add_patch(Rectangle((40, 1.02), 14, .05, color=O))
ax.text(21, 1.09, 'nuta 1 (koniec z $p_{off}$)', ha='center', fontsize=7); ax.text(47, 1.09, 'nuta 2 (koniec: spadek $p_{fr}$)', ha='center', fontsize=7); ax.set_ylim(0, 1.2)
ax.set(xlabel='klatka', ylabel='prawdopodobieństwo', title='dekoder dla jednego półtonu (dane poglądowe, nie z modelu)'); ax.legend(loc='center right', fontsize=7)
save('r10_dekoder')

# 11. harmonogram lr
fig, ax = plt.subplots(figsize=(6, 2.6)); st = np.arange(0, 36000)
lr = np.where(st < 1000, 1e-3 * (st + 1) / 1000, 1e-3 * .5 * (1 + np.cos(np.pi * np.clip((st - 1000) / 35000, 0, 1))))
ax.plot(st, lr, color=B); ax.set(xlabel='krok', ylabel='tempo uczenia $\\eta$', title='sesja 1: rozgrzewka (1000 kroków) + kosinus'); save('r11_lr')

# 12. dopasowanie nut
fig, ax = plt.subplots(figsize=(8, 2.8))
ref = [(.3, .9), (1.0, 1.6)]; est = [(.33, .85), (1.12, 1.5), (2.0, 2.4)]
for k, (a_, b_) in enumerate(ref): ax.add_patch(Rectangle((a_, 1 + .02), b_ - a_, .4, color=B)); ax.add_patch(Rectangle((a_ - .05, 1.45), .1, .08, color=G))
for k, (a_, b_) in enumerate(est): ax.add_patch(Rectangle((a_, .5), b_ - a_, .4, color=O))
ax.text(.02, 1.75, 'wzorzec 1: różnica początków 30 ms ≤ 50 ms → TP', fontsize=7); ax.text(1.0, 1.95, 'wzorzec 2: różnica 120 ms > 50 ms → FN', fontsize=7, color=R)
ax.text(.3, .35, 'system 1', fontsize=7); ax.text(1.12, .35, 'system 2 → FP', fontsize=7, color=R); ax.text(2.0, .35, 'system 3 → FP', fontsize=7, color=R)
ax.set(xlim=(0, 2.7), ylim=(.2, 2.15), xlabel='czas [s]', yticks=[.7, 1.2], yticklabels=['system', 'wzorzec'], title='dopasowanie: TP=1, FP=2, FN=1 → P=1/3, R=1/2, F1=0,4'); ax.grid(False)
save('r12_dopasowanie')

# 13. krzywa uczenia z epoki.csv
rows = list(csv.DictReader(open(os.path.join(ROOT, 'docs', 'wyniki', 'epoki.csv'), encoding='utf-8')))
ep = [int(r['epoka']) for r in rows]; v = [float(r['val_RAZEM_note_F1']) for r in rows]; ss = [r['sesja'] for r in rows]
fig, ax = plt.subplots(1, 2, figsize=(9, 3))
for s_, c in (('1', B), ('3', O), ('4', G)):
    xs = [e for e, q in zip(ep, ss) if q == s_]; ys = [y for y, q in zip(v, ss) if q == s_]; ax[0].plot(xs, ys, '.-', color=c, label='sesja ' + s_)
ax[0].set(xlabel='epoka', ylabel='F1 nut na walidacji [%]', ylim=(68, 91.5), title='walidacja'); ax[0].legend()
ax[1].plot(ep, [float(r['strata_onset']) for r in rows], color=B, label='początek'); ax[1].plot(ep, [float(r['strata_frame']) for r in rows], color=G, label='brzmi'); ax[1].plot(ep, [float(r['strata_offset']) for r in rows], color=R, label='koniec')
ax[1].set(xlabel='epoka', yscale='log', title='strata na uczeniu'); ax[1].legend()
save('r13_uczenie')

# 14. wyniki per instrument (sesja4_epoka81, makro)
rows = [r for r in csv.DictReader(open(os.path.join(ROOT, 'docs', 'wyniki', 'test_grupy.csv'), encoding='utf-8'))]
mods = sorted({r['model'] for r in rows}); mdl = 'sesja4_epoka81' if 'sesja4_epoka81' in mods else mods[-1]
g = [(r['grupa'], float(r['note_F1'])) for r in rows if r['model'] == mdl and r['uśrednienie'] == 'macro' and r['note_F1'] not in ('', 'nan')]
g.sort(key=lambda x: x[1]); fig, ax = plt.subplots(figsize=(7, 7.5))
ax.barh([a.replace('klasyka:', '').replace('solo:', '') for a, _ in g], [b for _, b in g], color=[O if 'GuitarSet' in a else B for a, _ in g])
ax.set(xlabel='F1 nut [%] (makro, test), model: ' + mdl, title='wyniki według grupy (pomarańczowe = prawdziwa gitara)'); ax.set_xlim(40, 100)
save('r14_instrumenty')

# 15. dekoder domyślny vs dostrojony
fig, ax = plt.subplots(figsize=(6.5, 2.8)); lab = ['F1 nut', 'F1 z końcem', 'F1 klatkowe', 'precyzja', 'czułość']
a_ = [85.9, 69.4, 88.5, 88.8, 84.2]; b_ = [86.6, 70.0, 87.3, 93.5, 82.1]; x = np.arange(5)
ax.bar(x - .2, a_, .4, color=B, label='domyślny'); ax.bar(x + .2, b_, .4, color=G, label='dostrojony'); ax.set_xticks(x); ax.set_xticklabels(lab); ax.set_ylim(60, 98); ax.legend()
for xx, u, w in zip(x, a_, b_): ax.text(xx - .2, u + .5, u, ha='center', fontsize=7); ax.text(xx + .2, w + .5, w, ha='center', fontsize=7)
ax.set_title('test 700 nagrań (makro): wpływ dostrojenia progów'); save('r15_dekoder_wyniki')

# ================= rysunki do Części I (tłumaczenie matematyki)
# 16. próbkowanie i aliasing
fig, ax = plt.subplots(1, 2, figsize=(9, 2.8))
tc = np.linspace(0, 0.002, 2000); ts = np.arange(0, 0.002, 1 / fs)
ax[0].plot(tc * 1000, np.sin(2 * np.pi * 2000 * tc), color=B, lw=1); ax[0].plot(ts * 1000, np.sin(2 * np.pi * 2000 * ts), 'o', color=O, ms=4)
ax[0].set(title='2000 Hz: ok. 5,5 próbki na okres', xlabel='czas [ms]')
ax[1].plot(tc * 1000, np.sin(2 * np.pi * 7000 * tc), color=B, lw=.6, label='ton 7000 Hz'); ax[1].plot(tc * 1000, -np.sin(2 * np.pi * 4025 * tc), color=R, lw=1, label='„duch” 4025 Hz')
ax[1].plot(ts * 1000, np.sin(2 * np.pi * 7000 * ts), 'o', color=O, ms=4); ax[1].legend(fontsize=7, loc='lower left')
ax[1].set(title='7000 Hz > Nyquist (5512,5): próbki pasują do 4025 Hz', xlabel='czas [ms]')
save('r16_probkowanie')

# 17. intuicja DFT
fig, ax = plt.subplots(1, 4, figsize=(11, 2.6)); tn = np.linspace(0, 1, 800, endpoint=False)
x = np.sin(2 * np.pi * 3 * tn) + .6 * np.sin(2 * np.pi * 5 * tn)
for c, kk in enumerate((3, 4, 5)):
    prod = x * np.sin(2 * np.pi * kk * tn)
    ax[c].plot(tn, prod, color=B, lw=.8); ax[c].axhline(prod.mean(), color=R, lw=1.5); ax[c].set_ylim(-2, 2)
    ax[c].set_title('sygnał × fala %d Hz\nśrednia (czerwona) = %.2f' % (kk, prod.mean()), fontsize=8); ax[c].set_xlabel('czas [s]')
ax[3].bar([3, 4, 5], [.5, 0, .3], color=G); ax[3].set(title='wynik: „ile którego tonu”\n(3 Hz: 1·½, 5 Hz: 0,6·½)', xlabel='częstotliwość testowa [Hz]', xticks=[3, 4, 5]); ax[3].title.set_fontsize(8)
fig.subplots_adjust(wspace=.35)
save('r17_dft')

# 18. decybele i normalizacja
fig, ax = plt.subplots(1, 2, figsize=(9, 2.8)); A = np.logspace(-4, 0, 300)
ax[0].semilogx(A, 20 * np.log10(A), color=B); ax[0].set(xlabel='amplituda $A$', ylabel='$L=20\\log_{10}A$ [dB]', title='decybele: mnożenie $\\to$ dodawanie')
for a_, c in ((.5, R), (.1, O), (.01, G)): ax[0].plot(a_, 20 * np.log10(a_), 'o', color=c); ax[0].annotate('%.1f dB' % (20 * np.log10(a_)), (a_, 20 * np.log10(a_)), (a_ * 1.3, 20 * np.log10(a_) - 6), fontsize=7)
L = np.linspace(-80, 10, 200); ax[1].plot(L, np.clip((L + 6) / 60 + 1, 0, 1.3), color=G)
ax[1].set(xlabel='$L$ [dB] (przy $L_{ref}=-6$ dB)', ylabel='cecha $X$', title='normalizacja: 0 = ref−60 dB, 1 = ref, przycięcie 1,3'); ax[1].plot([-26], [.667], 'o', color=R); ax[1].annotate('$A=0{,}05$: $X=0{,}667$', (-26, .667), (-70, 1.0), arrowprops=dict(arrowstyle='->'), fontsize=8)
save('r18_decybele')

# 19. konwolucja krok po kroku
fig, ax = plt.subplots(2, 1, figsize=(8, 3.6)); xs_ = [1, 2, 3, 4, 5]
for a, d, ys in ((ax[0], 1, [-2, -2, -2, -2, 4]), (ax[1], 2, [-3, -4, -4, 2, 3])):
    a.axis('off'); a.set_xlim(-1, 12.5); a.set_ylim(-.3, 3.3)
    for i, v in enumerate(xs_): a.add_patch(Rectangle((i * 1.2, 2), 1, .8, fc='#e8f0fa', ec=K)); a.text(i * 1.2 + .5, 2.4, v, ha='center', va='center')
    for i, v in enumerate(ys): a.add_patch(Rectangle((i * 1.2, 0), 1, .8, fc='#fbd9b0', ec=K)); a.text(i * 1.2 + .5, .4, v, ha='center', va='center')
    i = 2
    for j, c in ((-d, G), (d, R)):
        jj = i + j
        if 0 <= jj < 5: a.annotate('', (i * 1.2 + .5, .85), (jj * 1.2 + .5, 1.95), arrowprops=dict(arrowstyle='-|>', color=c, lw=1.2))
    a.text(7.3, 2.4, 'x', fontsize=9, ha='left'); a.text(7.3, .4, 'y', fontsize=9)
    a.text(7.8, 1.5, ('$d=%d$: $y[i]=x[i-%d]-x[i+%d]$\nprzykład $i=2$ (trzeci element):\n$%d-%d=%d$' % (d, d, d, xs_[2 - d] if 2 - d >= 0 else 0, xs_[2 + d] if 2 + d < 5 else 0, ys[2])), fontsize=8, va='center')
save('r19_konwolucja')

# 20. softmax
fig, ax = plt.subplots(1, 3, figsize=(10, 2.7))
for a, z, tt in ((ax[0], np.array([.707, 0, .707]), 'logity $\\to$ wagi'), (ax[1], np.array([3, 1, 0.]), 'duże różnice: prawie „twardy” wybór'), (ax[2], np.array([2, 2, -np.inf, 2.]), 'maska $-\\infty$ → waga 0')):
    e = np.exp(z - z[np.isfinite(z)].max()); w_ = e / e.sum(); xx = np.arange(len(z))
    a.bar(xx - .2, np.where(np.isfinite(z), z, 0), .4, color='#bbb', label='logit'); a.bar(xx + .2, w_, .4, color=B, label='softmax')
    for q, v in zip(xx, w_): a.text(q + .2, v + .03, '%.2f' % v, ha='center', fontsize=7)
    a.set_title(tt, fontsize=8); a.set_xticks(xx)
ax[0].legend(fontsize=7)
save('r20_softmax')

# 21. LayerNorm i residual
fig, ax = plt.subplots(1, 3, figsize=(10, 2.7), gridspec_kw={'width_ratios': [1, 1, 1.2]})
z = np.array([1, 2, 3, 6.]); zn = (z - z.mean()) / z.std(); z2 = z * 100; zn2 = (z2 - z2.mean()) / z2.std()
ax[0].bar(range(4), z, color='#bbb'); ax[0].set_title('wejście $(1,2,3,6)$', fontsize=8)
ax[1].bar(range(4), zn, color=B, label='$(1,2,3,6)$'); ax[1].bar(np.arange(4) + .0, zn2, .3, color=O, alpha=.8, label='$(100..600)$ — to samo!'); ax[1].legend(fontsize=7); ax[1].set_title('po LayerNorm: średnia 0, wariancja 1', fontsize=8)
ax[2].axis('off'); ax[2].set_xlim(0, 10); ax[2].set_ylim(0, 6)
ax[2].add_patch(FancyBboxPatch((3.5, 1.7), 3, 1.6, boxstyle='round', fc='#fbd9b0', ec=K)); ax[2].text(5, 2.5, '$F$ (warstwa)', ha='center', va='center', fontsize=8)
ax[2].annotate('', (5, 1.7), (5, .4), arrowprops=dict(arrowstyle='->')); ax[2].text(5.2, .1, '$x$', fontsize=9)
ax[2].annotate('', (5, 4.7), (5, 3.3), arrowprops=dict(arrowstyle='->')); ax[2].text(5.2, 4.9, '$y=x+F(x)$', fontsize=9)
ax[2].annotate('', (1.5, 4.0), (1.5, .8), arrowprops=dict(arrowstyle='-', color=R, lw=1.5)); ax[2].plot([1.5, 4.7], [.8, .8], color=R, lw=1.5); ax[2].plot([1.5, 4.7], [4.0, 4.0], color=R, lw=1.5)
ax[2].text(0, 2.4, 'skrót\n(gradient\nlata tędy)', fontsize=7, color=R); ax[2].set_title('połączenie resztkowe', fontsize=8)
save('r21_ln_residual')

# 22. uwaga krok po kroku (T=4, d=2)
rng = np.random.default_rng(5); Tn = 4
Q = np.array([[1, 0], [0, 1], [1, 1], [.5, -.5]]); Kx = np.array([[1, 0], [0, 1], [1, 1], [-.5, .5]]); V = np.array([[1, 0], [0, 2], [3, 3], [1, -1.]])
S_ = Q @ Kx.T / math.sqrt(2); Aw = np.exp(S_) / np.exp(S_).sum(1, keepdims=True); Y = Aw @ V
fig, ax = plt.subplots(1, 4, figsize=(11, 2.9))
for a, M_, tt in ((ax[0], S_, '1) wyniki $q_i\\cdot k_j/\\sqrt{d}$'), (ax[1], Aw, '2) softmax po wierszu → wagi $a_{ij}$'), (ax[2], Y, '3) $y_i=\\sum_j a_{ij}v_j$')):
    a.imshow(M_, cmap='Blues', aspect='auto'); a.set_title(tt, fontsize=8); a.grid(False)
    for i in range(M_.shape[0]):
        for j in range(M_.shape[1]): a.text(j, i, '%.2f' % M_[i, j], ha='center', va='center', fontsize=8, color='k')
for a_ in ax[:3]: a_.set_yticks(range(4)); a_.set_yticklabels(['1', '2', '3', '4'])
for a_ in ax[:2]: a_.set_xticks(range(4)); a_.set_xticklabels(['1', '2', '3', '4'])
ax[2].set_xticks([0, 1]); ax[2].set_xticklabels(['1.', '2.'])
ax[0].set(xlabel='klucz $j$', ylabel='zapytanie $i$'); ax[1].set(xlabel='klucz $j$'); ax[2].set(xlabel='współrzędna wyniku')
ax[3].axis('off'); ax[3].text(0, .5, 'Wiersze wag sumują się do 1:\n' + '\n'.join('$\\Sigma_%d$ = %.2f' % (i + 1, Aw[i].sum()) for i in range(4)) + '\n\n$q_1$ najbardziej\npasuje do $k_1$ i $k_3$,\nwięc $y_1$ to głównie\nmieszanka $v_1$ i $v_3$.', fontsize=8, va='center')
save('r22_uwaga_kroki')

# 23. gradient: SGD vs Adam
fig, ax = plt.subplots(figsize=(5.6, 3.4)); gx, gy = np.meshgrid(np.linspace(-1.2, 1.2, 200), np.linspace(-1.2, 1.2, 200)); Lf = lambda x, y: .5 * (x ** 2 + 20 * y ** 2)
ax.contour(gx, gy, Lf(gx, gy), 14, cmap='Greys', linewidths=.6)
def run(opt):
    th = np.array([-1., 1.]); path = [th.copy()]; m = np.zeros(2); v = np.zeros(2)
    for t in range(1, 60):
        g = np.array([th[0], 20 * th[1]])
        if opt == 'sgd': th = th - .09 * g
        else:
            m = .9 * m + .1 * g; v = .999 * v + .001 * g ** 2; th = th - .06 * (m / (1 - .9 ** t)) / (np.sqrt(v / (1 - .999 ** t)) + 1e-8)
        path.append(th.copy())
    return np.array(path)
for o, c, lab in (('sgd', R, 'spadek gradientu (zygzak)'), ('adam', G, 'Adam (skala po osiach)')):
    pa = run(o); ax.plot(pa[:, 0], pa[:, 1], '.-', color=c, ms=3, lw=.8, label=lab)
ax.plot(0, 0, '*', color=B, ms=12); ax.legend(fontsize=7); ax.set(xlabel='$\\theta_1$ (płaska dolina)', ylabel='$\\theta_2$ (stromo)', title='dwa parametry o różnej skali gradientu'); ax.grid(False)
save('r23_optymalizacja')

# 24. PR + izolinie F1
fig, ax = plt.subplots(1, 2, figsize=(9, 3.2))
prc = np.linspace(0, 1, 100); P_ = 1 - .35 * prc ** 2.5 - .05 * prc; ax[0].plot(prc, P_, color=B); ax[0].fill_between(prc, 0, P_, alpha=.15, color=B)
ax[0].set(xlabel='czułość $R$', ylabel='precyzja $P$', title='krzywa P–R; pole pod nią = AP', ylim=(0, 1.05)); ax[0].text(.3, .35, 'AP = $\\sum(R_n-R_{n-1})P_n$', fontsize=8)
Rg, Pg = np.meshgrid(np.linspace(.01, 1, 200), np.linspace(.01, 1, 200)); F = 2 * Rg * Pg / (Rg + Pg)
cs = ax[1].contourf(Rg, Pg, F, np.linspace(0, 1, 11), cmap='viridis'); plt.colorbar(cs, ax=ax[1], label='$F_1$'); ax[1].plot([.8], [.8], 'o', color='w'); ax[1].annotate('P=R=0,8 → F1=0,8', (.8, .8), (.2, .9), color='w', fontsize=8, arrowprops=dict(arrowstyle='->', color='w'))
ax[1].plot([.99], [.1], 'o', color='r'); ax[1].annotate('P=0,1, R=0,99 → F1=0,18\n(F1 karze za nierówność)', (.99, .1), (.28, .08), color='w', fontsize=7); ax[1].set(xlabel='$R$', ylabel='$P$', title='F1 = średnia harmoniczna'); ax[1].grid(False)
save('r24_pr_f1')

# 25. kalibracja i bootstrap
fig, ax = plt.subplots(1, 2, figsize=(9, 3)); rg = np.random.default_rng(1)
pc = np.linspace(.05, .95, 10); acc = np.clip(pc + .05 * np.sin(6 * pc) + rg.normal(0, .015, 10), 0, 1)
ax[0].plot([0, 1], [0, 1], '--', color=K, lw=.8); ax[0].bar(pc, acc, .08, color=B, alpha=.7)
for a_, b_ in zip(pc, acc): ax[0].plot([a_, a_], [a_, b_], color=R)
ax[0].set(xlabel='średnie przewidywanie w przedziale', ylabel='faktyczna częstość', title='ECE: średnia ważona czerwonych odcinków\n(liczby tu są poglądowe)'); ax[0].title.set_fontsize(8)
vals = rg.normal(.86, .08, 80).clip(0, 1); bm = np.array([rg.choice(vals, len(vals)).mean() for _ in range(3000)]); lo, hi = np.percentile(bm, [2.5, 97.5])
ax[1].hist(bm, 40, color=G, alpha=.8); ax[1].axvline(lo, color=R); ax[1].axvline(hi, color=R); ax[1].axvline(vals.mean(), color=K, ls='--')
ax[1].set(xlabel='średnia z próby bootstrap', title='bootstrap: 3000 losowań z zwracaniem\nczerwone = 95 % przedział (poglądowe dane)'); ax[1].title.set_fontsize(8)
save('r25_ece_bootstrap')

print('ok', len(os.listdir(OUT)))
