#!/usr/bin/env python3
"""prepare.py - etap A na Kaggle (CPU, bez limitu GPU): dane gen 6 + gotowe cechy HCQT.

Kroki: korpus MIDI (MAESTRO + music21) -> nagrania gen_classical (train / validation / test, utwór zawsze w jednym zbiorze)
-> środowiska gitarowe gen_env -> GuitarSet (zenodo) -> cechy HCQT gen 6 (float16, równolegle) -> manifesty JSONL.
Wyjście (<out>, domyślnie /kaggle/working/dane): feat/<źródło>/<id>.npy, ann/<źródło>/<id>.(truth.json|jams),
manifest_<źródło>.jsonl (format adaptera 'manifest' w tools/gen6/data.py), summary.json. Pliki .wav zostają w katalogu roboczym.

  python3 tools/gen6/kaggle/prepare.py [--out DIR] [--work DIR] [--versions 2] [--clips 1] [--env 900] [--no-guitarset]
Ograniczenie Kaggle: /kaggle/working do 20 GB, cechy ok. 1,9 MB na 15 s nagrania.
"""
import argparse, glob, json, os, shutil, subprocess, sys, time, urllib.request, zipfile, zlib
from multiprocessing import Pool

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, ROOT)
GS_URL = 'https://zenodo.org/records/3371780/files/%s?download=1'
T0 = time.time()


def log(*a):
    print('[%6.0f s]' % (time.time() - T0), *a, flush=True)


def sh(cmd, **kw):
    log('$', cmd if isinstance(cmd, str) else ' '.join(cmd))
    subprocess.run(cmd, check=True, shell=isinstance(cmd, str), cwd=ROOT, **kw)


def download(url, dst):
    if os.path.exists(dst):
        return dst
    log('pobieram', url)
    tmp = dst + '.part'
    with urllib.request.urlopen(url, timeout=600) as r, open(tmp, 'wb') as f:
        shutil.copyfileobj(r, f, 1 << 20)
    os.replace(tmp, dst)
    return dst


def feat_job(args):
    wav, dst = args
    from tools.gen6.config import FeatureConfig
    from tools.gen6.audio import load_audio
    from tools.gen6.features import hcqt
    import numpy as np
    if os.path.exists(dst):
        return dst, int(np.load(dst, mmap_mode='r').shape[0]), None
    try:
        cfg = FeatureConfig()
        X = hcqt(load_audio(wav, cfg.sr, cfg.frontend), cfg).astype(np.float16)
        tmp = dst[:-4] + '.tmp.npy'
        np.save(tmp, X)
        os.replace(tmp, dst)
        return dst, len(X), None
    except Exception as e:
        return dst, 0, repr(e)


def use_input(inp, W):
    """Notatnik Kaggle bez internetu: korpus i GuitarSet z dołączonego zbioru danych (zip albo rozpakowane)."""
    if not os.path.isdir(inp):
        return
    def unzip(z, dst):
        os.makedirs(dst, exist_ok=True)
        log('rozpakowuję', z, '->', dst)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(dst)
    def flat(dst, pattern):  # pliki pasujące do wzorca z dowolnej głębokości -> dst (dowiązania)
        os.makedirs(dst, exist_ok=True)
        for f in glob.glob(os.path.join(W, '_in', '**', pattern), recursive=True) + glob.glob(os.path.join(inp, '**', pattern), recursive=True):
            t = os.path.join(dst, os.path.basename(f))
            if not os.path.exists(t):
                os.symlink(os.path.abspath(f), t)
    for z in glob.glob(os.path.join(inp, '**', '*.zip'), recursive=True):
        unzip(z, os.path.join(W, '_in', os.path.basename(z)[:-4]))
    kor = os.path.join(W, 'korpus')
    if not os.path.exists(os.path.join(kor, 'manifest.csv')):
        hits = [h for h in glob.glob(os.path.join(W, '_in', '**', 'manifest.csv'), recursive=True) +
                glob.glob(os.path.join(inp, '**', 'manifest.csv'), recursive=True) if os.path.isdir(os.path.join(os.path.dirname(h), 'midi'))]
        if hits:
            os.makedirs(W, exist_ok=True)
            if os.path.lexists(kor):
                os.remove(kor)
            os.symlink(os.path.dirname(os.path.abspath(hits[0])), kor)
            log('korpus z wejścia:', hits[0])
    gs = os.path.join(W, 'guitarset')
    flat(os.path.join(gs, 'annotation'), '*.jams')
    flat(os.path.join(gs, 'audio_mono-mic'), '*_mic.wav')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='/kaggle/working/dane')
    ap.add_argument('--work', default='/tmp/g6')
    ap.add_argument('--versions', type=int, default=2)
    ap.add_argument('--clips', type=int, default=1)
    ap.add_argument('--val-versions', type=int, default=2)
    ap.add_argument('--len', nargs=2, default=['10', '20'])
    ap.add_argument('--guitar', default='0.35')
    ap.add_argument('--limit', type=int, default=0, help='najwyżej N utworów na zbiór (próba)')
    ap.add_argument('--env', type=int, default=900, help='nagrań środowisk gitarowych gen 4')
    ap.add_argument('--no-guitarset', action='store_true')
    ap.add_argument('--no-classical', action='store_true', help='bez korpusu i nagrań klasycznych (np. sam GuitarSet)')
    ap.add_argument('--seed-base', type=int, default=1, help='ziarno nagrań train (validation +1000, test +2000); inne = nowe nagrania')
    ap.add_argument('--env-seed', type=int, default=50000, help='pierwsze ziarno środowisk gen_env')
    ap.add_argument('--only-train', action='store_true', help='tylko zbiór train (dodatkowe dane; walidacja i test z pierwszego zestawu)')
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 4)
    ap.add_argument('--input', default='/kaggle/input', help='dane wejściowe bez internetu: korpus.zip, annotation.zip, '
                    'audio_mono-mic.zip (albo rozpakowane katalogi) gdziekolwiek pod tym katalogiem')
    a = ap.parse_args()
    W, O = a.work, a.out
    os.makedirs(W, exist_ok=True); os.makedirs(O, exist_ok=True); os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
    use_input(a.input, W)

    # 1. korpus MIDI
    if not a.no_classical and not os.path.exists(os.path.join(W, 'korpus', 'manifest.csv')):
        try:
            import music21  # noqa: F401
        except ImportError:
            sh([sys.executable, '-m', 'pip', 'install', '-q', 'music21'])
        cmd = [sys.executable, 'tools/gen6/fetch_classical.py', os.path.join(W, 'korpus'), '--jobs', str(a.jobs)]
        sh(cmd + (['--limit', str(a.limit * 3)] if a.limit else []))
    # 2. generatory
    sh('g++ -std=c++17 -O2 -pthread tools/gen_classical.cpp -o build/gen_classical')
    sh('g++ -std=c++17 -O2 tools/gen_env.cpp -o build/gen_env')
    # 3. nagrania klasyczne
    seed = a.seed_base
    for split in (('train',) if a.only_train else ('train', 'validation', 'test')):
        d = os.path.join(W, split)
        if not a.no_classical and not os.path.exists(os.path.join(d, 'index.csv')):
            v, c = (a.versions, a.clips) if split == 'train' else (a.val_versions, 1)
            cmd = ['./build/gen_classical', os.path.join(W, 'korpus', 'manifest.csv'), os.path.join(W, 'korpus'), d, '--split', split,
                   '--seed', str(seed), '--versions', str(v), '--clips', str(c), '--len', *a.len, '--jobs', str(a.jobs), '--guitar', a.guitar]
            sh(cmd + (['--limit', str(a.limit)] if a.limit else []))
        seed += 1000
    # 4. środowiska gitarowe (gen 4)
    if a.env:
        d = os.path.join(W, 'env')
        if len(glob.glob(os.path.join(d, '*.truth.json'))) < a.env:
            os.makedirs(d, exist_ok=True)
            per = (a.env + a.jobs - 1) // a.jobs
            procs = [subprocess.Popen(['./build/gen_env', d, str(a.env_seed + k * per), str(min(per, a.env - k * per))], cwd=ROOT,
                                      stdout=subprocess.DEVNULL) for k in range(a.jobs) if a.env - k * per > 0]
            for p in procs:
                p.wait()
            log('środowiska: %d nagrań' % len(glob.glob(os.path.join(d, '*.truth.json'))))
    # 5. GuitarSet
    gs = os.path.join(W, 'guitarset')
    if not a.no_guitarset:
        os.makedirs(gs, exist_ok=True)
        for name, sub in (('annotation.zip', 'annotation'), ('audio_mono-mic.zip', 'audio_mono-mic')):
            if not os.path.isdir(os.path.join(gs, sub)) or not os.listdir(os.path.join(gs, sub)):
                try:
                    z = download(GS_URL % name, os.path.join(gs, name))
                except OSError as e:  # brak internetu i brak GuitarSet na wejściu: uczenie bez niego
                    log('GuitarSet niedostępny (%s), pomijam' % e)
                    break
                os.makedirs(os.path.join(gs, sub), exist_ok=True)
                with zipfile.ZipFile(z) as zf:
                    for m in zf.infolist():
                        if m.is_dir():
                            continue
                        dst = os.path.join(gs, sub, os.path.basename(m.filename))
                        with zf.open(m) as s, open(dst, 'wb') as f:
                            shutil.copyfileobj(s, f)
                os.remove(z)

    # 6. lista przykładów: (źródło, id, wav, adnotacja, format, split, group)
    items = []
    for split, sp in (('train', 'train'), ('validation', 'val'), ('test', 'test')):
        for tp in sorted(glob.glob(os.path.join(W, split, '*.truth.json'))):
            i = os.path.basename(tp)[:-11]
            t = json.load(open(tp))
            grp = ('solo:' + t.get('instruments', '')) if t.get('ensemble') == 'solo' else t.get('ensemble', '')
            items.append(('klasyka', i, tp[:-11] + '.wav', tp, 'truth_json', sp, grp, t.get('piece')))
    for tp in sorted(glob.glob(os.path.join(W, 'env', '*.truth.json'))):
        i = os.path.basename(tp)[:-11]
        sp = 'train' if a.only_train else ('val' if zlib.crc32(i.encode()) % 10 == 0 else 'train')
        items.append(('srodowiska', i, tp[:-11] + '.wav', tp, 'truth_json', sp, 'env', None))
    for jp in sorted(glob.glob(os.path.join(gs, 'annotation', '*.jams'))):
        i = os.path.basename(jp)[:-5]
        sp = 'test' if i[:3] in ('03_', '04_', '05_') else ('val' if i.startswith('02_Funk') else 'train')
        items.append(('guitarset', i, os.path.join(gs, 'audio_mono-mic', i + '_mic.wav'), jp, 'jams', sp,
                      'comp' if i.endswith('comp') else 'solo', None))
    items = [it for it in items if os.path.exists(it[2])]
    log('przykładów: %d, liczę cechy (%d procesów)' % (len(items), a.jobs))

    # 7. cechy
    jobs = []
    for src, i, wav, ann, fmt, sp, grp, piece in items:
        os.makedirs(os.path.join(O, 'feat', src), exist_ok=True)
        jobs.append((wav, os.path.join(O, 'feat', src, i + '.npy')))
    lens, bad = {}, 0
    with Pool(a.jobs) as pool:
        for k, (dst, T, err) in enumerate(pool.imap_unordered(feat_job, jobs, chunksize=4)):
            if err:
                bad += 1; log('błąd cech', dst, err)
            lens[dst] = T
            if (k + 1) % 250 == 0 or k + 1 == len(jobs):
                log('cechy %d/%d (błędów %d)' % (k + 1, len(jobs), bad))

    # 8. adnotacje + manifesty
    summary, fhs = {}, {}
    for (src, i, wav, ann, fmt, sp, grp, piece), (_, dst) in zip(items, jobs):
        if not lens.get(dst):
            continue
        ad = os.path.join(O, 'ann', src); os.makedirs(ad, exist_ok=True)
        an = os.path.join(ad, os.path.basename(ann))
        if not os.path.exists(an):
            shutil.copy(ann, an)
        if src not in fhs:
            fhs[src] = open(os.path.join(O, 'manifest_%s.jsonl' % src), 'w')
        rec = {'id': i, 'features': os.path.relpath(dst, O), 'features_hop': 256, 'annotation': os.path.relpath(an, O),
               'format': fmt, 'split': sp, 'group': grp}
        if piece:
            rec['piece'] = piece
        fhs[src].write(json.dumps(rec, ensure_ascii=False) + '\n')
        s = summary.setdefault(src, {}).setdefault(sp, {'n': 0, 'frames': 0})
        s['n'] += 1; s['frames'] += lens[dst]
    for f in fhs.values():
        f.close()
    for src in summary:
        for sp in summary[src]:
            summary[src][sp]['hours'] = round(summary[src][sp]['frames'] * 256 / 11025 / 3600, 2)
    json.dump({'summary': summary, 'args': vars(a), 'sec': round(time.time() - T0)}, open(os.path.join(O, 'summary.json'), 'w'), indent=1)
    log(json.dumps(summary, indent=1))
    du = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(O) for f in fs)
    log('gotowe: %.1f GB w %s' % (du / 1e9, O))


if __name__ == '__main__':
    main()
