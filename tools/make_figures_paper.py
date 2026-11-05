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
print('ok', os.listdir(OUT))
