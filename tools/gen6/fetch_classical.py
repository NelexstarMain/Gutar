#!/usr/bin/env python3
"""fetch_classical.py - korpus muzyki klasycznej jako MIDI dla generacji 6.

Źródła (razem ok. 3200 utworów):
  * MAESTRO v3.0.0 (Hawthorne i in. 2019, CC BY-NC-SA 4.0): 1276 wykonań fortepianowych MIDI z konkursu Piano-e-Competition
    (Bach, Beethoven, Chopin, Schubert, Liszt, Mozart, Haydn, Debussy, Rachmaninow, …), z własnym podziałem train/validation/test
    (ten sam utwór nigdy nie trafia do dwóch zbiorów).
  * korpus music21 (partytury MusicXML / Humdrum / ABC z wieloma głosami): chorały i inne utwory Bacha, msze Palestriny, madrygały
    Monteverdiego, muzyka trecento, Josquin, Beethoven, Mozart, Haydn, Händel, Corelli, Schumannowie, Schubert, Weber, Verdi,
    Schönberg, Webern, Joplin. Każda partia trafia do osobnej ścieżki MIDI (generator może dać każdemu głosowi inny instrument).
    Podział: skrót ścieżki pliku (90 / 5 / 5 %), wszystkie wersje jednego utworu zostają w jednym zbiorze.

Wyjście:
  <katalog>/midi/maestro/<id>.mid, <katalog>/midi/m21/<id>.mid
  <katalog>/manifest.csv: id, źródło, kompozytor, tytuł, zbiór (train/validation/test), czas [s], liczba nut, liczba głosów, plik

Użycie:  python3 tools/gen6/fetch_classical.py korpus6 [--no-maestro] [--no-m21] [--jobs 4] [--limit N]
Wymaga: pip install music21 (tylko dla części music21; MAESTRO pobierane wprost).
"""
import argparse, csv, hashlib, io, os, re, sys, urllib.request, zipfile
from concurrent.futures import ProcessPoolExecutor

MAESTRO_URL = 'https://storage.googleapis.com/magentadata/datasets/maestro/v3.0.0/maestro-v3.0.0-midi.zip'

# katalogi korpusu music21 z muzyką klasyczną (bez pieśni ludowych i ćwiczeń); nazwa katalogu -> kompozytor
M21_DIRS = {
    'bach': 'Johann Sebastian Bach', 'palestrina': 'Giovanni Pierluigi da Palestrina', 'monteverdi': 'Claudio Monteverdi',
    'trecento': 'trecento (różni)', 'josquin': 'Josquin des Prez', 'beethoven': 'Ludwig van Beethoven',
    'mozart': 'Wolfgang Amadeus Mozart', 'haydn': 'Joseph Haydn', 'handel': 'Georg Friedrich Händel',
    'corelli': 'Arcangelo Corelli', 'cpebach': 'Carl Philipp Emanuel Bach', 'schumann_robert': 'Robert Schumann',
    'schumann_clara': 'Clara Schumann', 'schubert': 'Franz Schubert', 'weber': 'Carl Maria von Weber', 'verdi': 'Giuseppe Verdi',
    'schoenberg': 'Arnold Schönberg', 'webern': 'Anton Webern', 'joplin': 'Scott Joplin', 'chopin': 'Fryderyk Chopin',
    'ciconia': 'Johannes Ciconia', 'luca': 'Luca Marenzio', 'lusitano': 'Vicente Lusitano', 'beach': 'Amy Beach',
}
M21_EXT = ('.mxl', '.xml', '.musicxml', '.krn', '.abc')


def split_of(key):
    h = int(hashlib.sha1(key.encode()).hexdigest()[:8], 16) % 100
    return 'test' if h < 5 else ('validation' if h < 10 else 'train')


def midi_stats(path):
    """(czas [s], liczba nut, liczba głosów) z pliku MIDI - prosty parser, bez zależności."""
    d = open(path, 'rb').read()
    if d[:4] != b'MThd':
        return 0.0, 0, 0
    ntrk, div = int.from_bytes(d[10:12], 'big'), int.from_bytes(d[12:14], 'big')
    p, events, voices = 14, [], set()
    for ti in range(ntrk):
        if d[p:p + 4] != b'MTrk':
            break
        ln = int.from_bytes(d[p + 4:p + 8], 'big'); q, end, tick, rs = p + 8, p + 8 + ln, 0, 0
        while q < end:
            v = 0
            while True:
                b = d[q]; q += 1; v = (v << 7) | (b & 127)
                if b < 128: break
            tick += v
            st = d[q]
            if st == 0xFF:
                typ = d[q + 1]; q += 2; l = 0
                while True:
                    b = d[q]; q += 1; l = (l << 7) | (b & 127)
                    if b < 128: break
                if typ == 0x51: events.append((tick, 'T', int.from_bytes(d[q:q + 3], 'big')))
                q += l; continue
            if st in (0xF0, 0xF7):
                q += 1; l = 0
                while True:
                    b = d[q]; q += 1; l = (l << 7) | (b & 127)
                    if b < 128: break
                q += l; continue
            if st & 0x80: rs = st; q += 1
            hi = rs & 0xF0
            n = 1 if hi in (0xC0, 0xD0) else 2
            if hi == 0x90 and d[q + 1] > 0 and (rs & 15) != 9:
                events.append((tick, 'N', 0)); voices.add((ti, rs & 15))
            q += n
        p = end
    events.sort(key=lambda e: e[0])
    t, last, tempo, nn = 0.0, 0, 500000, 0
    for tick, k, val in events:
        t += (tick - last) * tempo / 1e6 / div; last = tick
        if k == 'T': tempo = val
        else: nn += 1
    return round(t, 1), nn, len(voices)


def fetch_maestro(out, rows, limit):
    os.makedirs(os.path.join(out, 'midi', 'maestro'), exist_ok=True)
    zpath = os.path.join(out, 'maestro-v3.0.0-midi.zip')
    if not os.path.exists(zpath):
        print('pobieram MAESTRO (ok. 57 MB)…', flush=True)
        urllib.request.urlretrieve(MAESTRO_URL, zpath)
    z = zipfile.ZipFile(zpath)
    meta = [n for n in z.namelist() if n.endswith('.csv')][0]
    for i, r in enumerate(csv.DictReader(io.TextIOWrapper(z.open(meta), encoding='utf-8'))):
        if limit and i >= limit: break
        pid = 'mae%04d' % i
        dst = os.path.join(out, 'midi', 'maestro', pid + '.mid')
        if not os.path.exists(dst):
            src = [n for n in z.namelist() if n.endswith(r['midi_filename'])][0]
            open(dst, 'wb').write(z.read(src))
        dur, nn, nv = midi_stats(dst)
        rows.append([pid, 'maestro', r['canonical_composer'], r['canonical_title'], r['split'], dur, nn, nv, os.path.relpath(dst, out)])


def _convert(job):
    src, dst = job
    if os.path.exists(dst):
        return dst, None
    try:
        from music21 import converter
        s = converter.parse(src)
        if hasattr(s, 'scores'):  # Opus (np. plik ABC z wieloma melodiami): pierwszy utwór
            s = s.scores[0] if len(s.scores) else s
        s.write('midi', fp=dst)
        return dst, None
    except Exception as e:  # uszkodzone / nieobsługiwane pliki pomijamy
        return dst, '%s: %s' % (type(e).__name__, str(e)[:80])


def fetch_m21(out, rows, jobs, limit):
    import music21
    base = os.path.join(os.path.dirname(music21.__file__), 'corpus')
    os.makedirs(os.path.join(out, 'midi', 'm21'), exist_ok=True)
    todo = []
    for d, comp in sorted(M21_DIRS.items()):
        for root, _, files in os.walk(os.path.join(base, d)):
            for f in sorted(files):
                if f.endswith(M21_EXT):
                    rel = os.path.relpath(os.path.join(root, f), base)
                    pid = 'm21_' + re.sub(r'[^A-Za-z0-9]+', '_', os.path.splitext(rel)[0]).strip('_')[:60]
                    todo.append((os.path.join(root, f), os.path.join(out, 'midi', 'm21', pid + '.mid'), pid, comp, rel))
    if limit: todo = todo[:limit]
    print('music21: %d partytur do konwersji' % len(todo), flush=True)
    bad = 0
    with ProcessPoolExecutor(jobs) as ex:
        for k, ((dst, err), t) in enumerate(zip(ex.map(_convert, [(a, b) for a, b, *_ in todo], chunksize=4), todo)):
            if err:
                bad += 1; continue
            dur, nn, nv = midi_stats(dst)
            if nn < 8 or dur < 4: continue
            rows.append([t[2], 'music21', t[3], t[4], split_of(t[4]), dur, nn, nv, os.path.relpath(dst, out)])
            if (k + 1) % 200 == 0: print('  %d/%d' % (k + 1, len(todo)), flush=True)
    print('music21: pominięto %d plików, których nie dało się przeczytać' % bad)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--no-maestro', action='store_true')
    ap.add_argument('--no-m21', action='store_true')
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 2)
    ap.add_argument('--limit', type=int, default=0, help='najwyżej N utworów z każdego źródła (do prób)')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rows = []
    if not a.no_maestro: fetch_maestro(a.out, rows, a.limit)
    if not a.no_m21: fetch_m21(a.out, rows, a.jobs, a.limit)
    with open(os.path.join(a.out, 'manifest.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['id', 'source', 'composer', 'title', 'split', 'dur', 'notes', 'voices', 'file'])
        w.writerows(rows)
    by = {}
    for r in rows: by[(r[1], r[4])] = by.get((r[1], r[4]), 0) + 1
    print('zapisano manifest: %d utworów, %.1f h muzyki' % (len(rows), sum(r[5] for r in rows) / 3600))
    for k in sorted(by): print('  %-8s %-10s %5d' % (k[0], k[1], by[k]))


if __name__ == '__main__':
    main()
