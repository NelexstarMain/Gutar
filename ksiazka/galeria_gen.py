"""Buduje galeria.pdf: wszystkie rysunki książki z numerami (jak w książce) i podpisami."""
import re, glob
out=[r"\documentclass[11pt,a4paper]{book}", r"\input{preambula.tex}",
     r"\renewcommand{\cref}[1]{\textit{[odn.]}}\renewcommand{\Cref}[1]{\textit{[odn.]}}\renewcommand{\ref}[1]{?}\renewcommand{\eqref}[1]{(?)}",
     r"\pagestyle{empty}",
     r"\renewcommand{\sidecaption}[1]{\par\footnotesize #1}",
     r"\begin{document}", r"\sloppy"]
n=0
for f in sorted(glob.glob('rozdzial-*.tex')):
    ch=int(re.search(r'(\d+)',f).group(1)); s=open(f,encoding='utf-8').read()
    for k,m in enumerate(re.finditer(r'\\begin\{(figure\*?)\}(?:\[[^\]]*\])?(.*?)\\end\{\1\}',s,re.S),1):
        body=m.group(2); n+=1
        cap=re.search(r'\\(?:side)?caption\{(.*?)\\label',body,re.S)
        cap=cap.group(1).rstrip().rstrip('}') if cap else ''
        art=re.sub(r'\\(?:side)?caption\{.*',  '', body, flags=re.S)
        art=art.replace(r'\centering','')
        art=re.sub(r'width=[0-9.]*\\linewidth','width=0.8\\\\linewidth',art)
        out.append(r"\par\vspace{4mm}\noindent{\Large\bfseries Rysunek %d.%d}\quad{\small(plik: rozdzial-%02d.tex)}\par\smallskip"%(ch,k,ch))
        out.append(r"\begin{center}"+art+r"\end{center}")
        out.append(r"{\footnotesize "+cap+r"}\par\bigskip\hrule")
        out.append(r"\clearpage" if n%2==0 else "")
out.append(r"\end{document}")
open('galeria.tex','w',encoding='utf-8').write('\n'.join(out)); print(n,'rysunków')
