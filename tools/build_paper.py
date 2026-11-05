"""Składa docs/PRACA_NAUKOWA.pdf (pandoc + XeLaTeX). Znaczniki [[fig:nazwa]] w tekście są zamieniane na numer rysunku
(kolejność występowania obrazków rysunki/<nazwa>.png). Użycie: python3 tools/build_paper.py"""
import os, re, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'docs')
src = open(os.path.join(D, 'PRACA_NAUKOWA.md'), encoding='utf-8').read()
order = re.findall(r'rysunki/(r\d+_\w+)\.png', src)
num = {n: i + 1 for i, n in enumerate(dict.fromkeys(order))}
def sub(m):
    if m.group(1) not in num: sys.exit('brak rysunku ' + m.group(1))
    return str(num[m.group(1)])
tmp = os.path.join(D, '.build_praca.md')
open(tmp, 'w', encoding='utf-8').write(re.sub(r'\[\[fig:(\w+)\]\]', sub, src))
cmd = ['pandoc', tmp, '-s', '--pdf-engine=xelatex', '--toc', '--toc-depth=2', '-V', 'lang=pl', '-V', 'mainfont=Latin Modern Roman',
       '-V', 'sansfont=Latin Modern Sans', '-V', 'monofont=Latin Modern Mono', '-V', 'mathfont=Latin Modern Math',
       '-V', 'geometry:a4paper,margin=2.4cm', '-V', 'fontsize=11pt', '-V', 'linestretch=1.1', '-H', os.path.join(D, 'paper_header.tex'),
       '--resource-path', D, '-o', os.path.join(D, 'PRACA_NAUKOWA.pdf')] + sys.argv[1:]
try:
    subprocess.run(cmd, check=True, cwd=D)
finally:
    os.remove(tmp)
