#!/usr/bin/env python3
"""push.py - wysyła etap A (dane, CPU) albo B (uczenie, GPU T4) jako notatnik-skrypt Kaggle.

  export KAGGLE_API_TOKEN=...            (albo ~/.kaggle/kaggle.json; klucza nie zapisujemy w repozytorium)
  python3 tools/gen6/kaggle/push.py dane      [--user NAZWA] [--args "--versions 2 --clips 1"]
  python3 tools/gen6/kaggle/push.py trening   [--user NAZWA] [--args "--hours 11"]
  python3 tools/gen6/kaggle/push.py dalej     (druga sesja 12 h: dalsze uczenie od last.pt z wyniku 'trening', nowy cykl lr)
  kaggle kernels status NAZWA/gutar-gen6-dane ; kaggle kernels output NAZWA/gutar-gen6-trening -p wynik/

Kod (src/, tools/, bez danych) jest wklejany do skryptu jako tar.gz w base64, więc notatnik nie potrzebuje dostępu do GitHuba.
Etap B czyta wynik etapu A (kernel_sources), więc wysyłaj go dopiero, gdy A skończy się powodzeniem.
Etap A dostaje zbiór danych <użytkownik>/gutar-gen6-korpus (korpus MIDI z fetch_classical.py zapakowany jako korpus.zip),
etap B <użytkownik>/gutar-guitarset-czesci (annotation.zip i audio_00..05.zip; jeden plik 626 MB Kaggle nie przetwarzał), bo notatnik bez weryfikacji telefonu nie ma internetu.
"""
import argparse, base64, io, json, os, subprocess, sys, tarfile, tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SLUG = {'dane': 'gutar-gen6-dane', 'dane2': 'gutar-gen6-dane2', 'trening': 'gutar-gen6-trening', 'dalej': 'gutar-gen6-trening-dalej', 'piezo': 'gutar-gen6-piezo'}
TITLE = {'dane': 'Gutar gen6 dane', 'dane2': 'Gutar gen6 dane2', 'trening': 'Gutar gen6 trening', 'dalej': 'Gutar gen6 trening dalej', 'piezo': 'Gutar gen6 piezo'}

STUB = r'''# Gitara Słuchacz, generacja 6: %(what)s (wygenerowane przez tools/gen6/kaggle/push.py)
import base64, io, os, subprocess, sys, tarfile
CODE = "%(code)s"
dst = '/tmp/Gutar'
os.makedirs(dst, exist_ok=True)
tarfile.open(fileobj=io.BytesIO(base64.b64decode(CODE)), mode='r:gz').extractall(dst)
os.chdir(dst)
subprocess.run('nvidia-smi || true; nproc; free -g; df -h /tmp /kaggle/working; find /kaggle/input -maxdepth 3 | head -50', shell=True)
subprocess.run([sys.executable, '-u'] + %(cmd)r, check=True)
'''


def pack():
    files = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', 'src', 'tools', 'build.sh'], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.split()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tf:
        for f in files:
            if '__pycache__' in f or f.startswith('tools/baseline/') or f.startswith('tools/gen6/server/model/') or not os.path.isfile(os.path.join(ROOT, f)):
                continue
            tf.add(os.path.join(ROOT, f), f)
    return base64.b64encode(buf.getvalue()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['dane', 'dane2', 'trening', 'dalej', 'piezo'])
    ap.add_argument('--extra-data', default='', help='dodatkowe notatniki z danymi dla uczenia, np. gutar-gen6-dane2')
    ap.add_argument('--piezo-ds', default='gutar-piezo', help='dostrajanie: zbiór danych z nagraniami piezo, opisami i manifest_piezo.jsonl')
    ap.add_argument('--pretrained', default='gutar-gen6-trening-3', help='dostrajanie: notatnik z wstępnie nauczonym modelem (run/last.pt)')
    ap.add_argument('--slug', help='inna nazwa notatnika (np. kolejna sesja dalej)')
    ap.add_argument('--user', default=os.environ.get('KAGGLE_USERNAME'))
    ap.add_argument('--args', default='')
    ap.add_argument('--accelerator', default='NvidiaTeslaT4')
    ap.add_argument('--korpus', default='gutar-gen6-korpus', help='zbiór danych z korpus.zip (etap A)')
    ap.add_argument('--guitarset', default='', help='opcjonalny zbiór danych z GuitarSet dla etapu B; bez niego etap B pobiera GuitarSet z zenodo (wymaga internetu w notatniku)')
    a = ap.parse_args()
    if not a.user:
        out = subprocess.run(['kaggle', 'config', 'view'], capture_output=True, text=True).stdout
        a.user = next((l.split(':', 1)[1].strip() for l in out.splitlines() if 'username' in l), None)
    if not a.user:
        sys.exit('podaj --user (nazwa konta Kaggle)')
    script = 'tools/gen6/kaggle/prepare.py' if a.stage.startswith('dane') else 'tools/gen6/kaggle/train_kaggle.py'
    if a.stage == 'dane2':  # dodatkowe nagrania: inne ziarna, tylko train (walidacja i test zostają z pierwszego zestawu)
        a.args = ('--seed-base 7 --env-seed 90000 --versions 3 --clips 1 --len 8 16 --only-train --no-guitarset ' + a.args).strip()
    if a.stage == 'dalej':  # druga sesja: dalsze uczenie od last.pt z wyniku notatnika 'trening'
        a.args = ('--continue-from auto ' + a.args).strip()
    if a.stage == 'piezo':  # dostrajanie na piezo: krótka sesja, nowy cykl lr, wybór epoki po walidacji tylko na piezo
        a.args = ('--config tools/gen6/configs/gen6_piezo.json --continue-from auto --extend 60 --extend-lr 1.5e-4 --hours 2.5 --eval-hours 0.3 ' + a.args).strip()
    cmd = [script] + a.args.split()
    d = tempfile.mkdtemp(prefix='kaggle_' + a.stage + '_')
    slug = a.slug or SLUG[a.stage]
    code = pack()
    open(os.path.join(d, 'run.py'), 'w').write(STUB % {'what': a.stage, 'code': code, 'cmd': cmd})
    meta = {'id': '%s/%s' % (a.user, slug), 'title': TITLE.get(a.stage, slug) if not a.slug else slug.replace('-', ' '), 'code_file': 'run.py', 'language': 'python',
            'kernel_type': 'script', 'is_private': True, 'enable_gpu': not a.stage.startswith('dane'), 'enable_tpu': False,
            'enable_internet': True,
            'dataset_sources': ['%s/%s' % (a.user, ds) for ds in ((a.piezo_ds if a.stage == 'piezo' else a.korpus) if a.stage.startswith('dane') or a.stage == 'piezo' else a.guitarset).split(',') if ds], 'competition_sources': [],
            'kernel_sources': {'dane': [], 'dane2': [], 'trening': ['%s/%s' % (a.user, SLUG['dane'])],
                               'dalej': ['%s/%s' % (a.user, SLUG['dane']), '%s/%s' % (a.user, SLUG['trening'])],
                               'piezo': ['%s/%s' % (a.user, SLUG['dane']), '%s/%s' % (a.user, a.pretrained)]}[a.stage]
                              + ['%s/%s' % (a.user, x) for x in a.extra_data.split(',') if x and not a.stage.startswith('dane')]}
    json.dump(meta, open(os.path.join(d, 'kernel-metadata.json'), 'w'), indent=1)
    print('kod: %.0f kB, katalog %s' % (len(code) / 1024, d))
    push = ['kaggle', 'kernels', 'push', '-p', d]
    if not a.stage.startswith('dane'):
        push += ['--accelerator', a.accelerator]
    subprocess.run(push, check=True)


if __name__ == '__main__':
    main()
