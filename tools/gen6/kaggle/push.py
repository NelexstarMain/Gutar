#!/usr/bin/env python3
"""push.py - wysyła etap A (dane, CPU) albo B (uczenie, GPU T4) jako notatnik-skrypt Kaggle.

  export KAGGLE_API_TOKEN=...            (albo ~/.kaggle/kaggle.json; klucza nie zapisujemy w repozytorium)
  python3 tools/gen6/kaggle/push.py dane      [--user NAZWA] [--args "--versions 2 --clips 1"]
  python3 tools/gen6/kaggle/push.py trening   [--user NAZWA] [--args "--hours 11"]
  kaggle kernels status NAZWA/gutar-gen6-dane ; kaggle kernels output NAZWA/gutar-gen6-trening -p wynik/

Kod (src/, tools/, bez danych) jest wklejany do skryptu jako tar.gz w base64, więc notatnik nie potrzebuje dostępu do GitHuba.
Etap B czyta wynik etapu A (kernel_sources), więc wysyłaj go dopiero, gdy A skończy się powodzeniem.
"""
import argparse, base64, io, json, os, subprocess, sys, tarfile, tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SLUG = {'dane': 'gutar-gen6-dane', 'trening': 'gutar-gen6-trening'}
TITLE = {'dane': 'Gutar gen6 dane', 'trening': 'Gutar gen6 trening'}

STUB = r'''# Gitara Słuchacz, generacja 6: %(what)s (wygenerowane przez tools/gen6/kaggle/push.py)
import base64, io, os, subprocess, sys, tarfile
CODE = "%(code)s"
dst = '/tmp/Gutar'
os.makedirs(dst, exist_ok=True)
tarfile.open(fileobj=io.BytesIO(base64.b64decode(CODE)), mode='r:gz').extractall(dst)
os.chdir(dst)
subprocess.run('nvidia-smi || true; nproc; free -g; df -h /tmp /kaggle/working', shell=True)
subprocess.run([sys.executable, '-u'] + %(cmd)r, check=True)
'''


def pack():
    files = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', 'src', 'tools', 'build.sh'], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.split()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tf:
        for f in files:
            if '__pycache__' in f or f.startswith('tools/baseline/') or not os.path.isfile(os.path.join(ROOT, f)):
                continue
            tf.add(os.path.join(ROOT, f), f)
    return base64.b64encode(buf.getvalue()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['dane', 'trening'])
    ap.add_argument('--user', default=os.environ.get('KAGGLE_USERNAME'))
    ap.add_argument('--args', default='')
    ap.add_argument('--accelerator', default='NvidiaTeslaT4')
    a = ap.parse_args()
    if not a.user:
        out = subprocess.run(['kaggle', 'config', 'view'], capture_output=True, text=True).stdout
        a.user = next((l.split(':', 1)[1].strip() for l in out.splitlines() if 'username' in l), None)
    if not a.user:
        sys.exit('podaj --user (nazwa konta Kaggle)')
    script = 'tools/gen6/kaggle/prepare.py' if a.stage == 'dane' else 'tools/gen6/kaggle/train_kaggle.py'
    cmd = [script] + a.args.split()
    d = tempfile.mkdtemp(prefix='kaggle_' + a.stage + '_')
    code = pack()
    open(os.path.join(d, 'run.py'), 'w').write(STUB % {'what': a.stage, 'code': code, 'cmd': cmd})
    meta = {'id': '%s/%s' % (a.user, SLUG[a.stage]), 'title': TITLE[a.stage], 'code_file': 'run.py', 'language': 'python',
            'kernel_type': 'script', 'is_private': True, 'enable_gpu': a.stage == 'trening', 'enable_tpu': False,
            'enable_internet': True, 'dataset_sources': [], 'competition_sources': [],
            'kernel_sources': ['%s/%s' % (a.user, SLUG['dane'])] if a.stage == 'trening' else []}
    json.dump(meta, open(os.path.join(d, 'kernel-metadata.json'), 'w'), indent=1)
    print('kod: %.0f kB, katalog %s' % (len(code) / 1024, d))
    push = ['kaggle', 'kernels', 'push', '-p', d]
    if a.stage == 'trening':
        push += ['--accelerator', a.accelerator]
    subprocess.run(push, check=True)


if __name__ == '__main__':
    main()
