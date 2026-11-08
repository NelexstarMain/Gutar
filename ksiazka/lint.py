#!/usr/bin/env python3
"""Kontrola jakości źródeł książki: czy wszystko jest wyjaśnione, udowodnione i pokazane.

Użycie: python3 lint.py <katalog-z-rozdzialami>

Sprawdza dla każdego pliku rozdzial-*.tex / dodatek-*.tex:
  - każde twierdzenie/lemat/wniosek ma po sobie dowód (proof) albo jawne odesłanie
    do dodatku (\\dowodw{...}); dowód bez żadnego kroku uzasadnienia to za mało,
  - każda definicja ma w pobliżu przykład (przyklad lub naliczbach),
  - rozdział ma co najmniej 2 rysunki (tikzpicture / pgfplots / includegraphics),
  - rozdział ma ramkę intuicja i zadania sprawdz,
  - każdy rysunek (figure) ma \\caption i \\label.
Kod wyjścia 1, gdy są braki, żeby build można było zatrzymać.
"""
import re
import sys
from pathlib import Path

CLAIMS = ("twierdzenie", "lemat", "wniosek")


def strip_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", text)


def check(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    text = strip_comments(raw)
    issues = []

    # twierdzenia i dowody
    for env in CLAIMS:
        for m in re.finditer(rf"\\begin\{{{env}\}}", text):
            tail = text[m.end():]
            end = re.search(rf"\\end\{{{env}\}}", tail)
            if not end:
                issues.append(f"{path.name}: niezamknięte środowisko {env}")
                continue
            after = tail[end.end():end.end() + 400]
            # dowód może być poprzedzony ramką pomyslDowodu
            has_proof = re.search(r"\\begin\{proof\}", after) or re.search(r"\\dowodw\{", after)
            if not has_proof:
                line = text[:m.start()].count("\n") + 1
                issues.append(f"{path.name}:{line}: {env} bez dowodu (dodaj proof lub \\dowodw{{dodatek}})")

    for m in re.finditer(r"\\begin\{proof\}(.*?)\\end\{proof\}", text, re.S):
        body = m.group(1)
        if len(re.findall(r"\\\\|\\begin\{align|\\\[|\$", body)) < 3:
            line = text[:m.start()].count("\n") + 1
            issues.append(f"{path.name}:{line}: dowód wygląda na pusty lub zbyt krótki (brak kroków)")

    # definicje i przykłady
    n_def = len(re.findall(r"\\begin\{definicja\}", text))
    n_ex = len(re.findall(r"\\begin\{(przyklad|naliczbach)\}", text))
    if n_def and n_ex < n_def:
        issues.append(f"{path.name}: {n_def} definicji, ale tylko {n_ex} przykładów (każda definicja potrzebuje przykładu)")

    # rysunki
    n_vis = len(re.findall(r"\\begin\{(tikzpicture|axis)\}|\\includegraphics", text))
    if path.name.startswith("rozdzial") and n_vis < 2:
        issues.append(f"{path.name}: tylko {n_vis} rysunków; rozdział ma pokazywać, nie tylko mówić (min. 2)")

    # pliki wykresów muszą istnieć (uruchom build.sh, który generuje figures/*.pdf)
    for m in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", text):
        sciezka = path.parent / m.group(1)
        if not sciezka.exists():
            line = text[:m.start()].count("\n") + 1
            issues.append(f"{path.name}:{line}: brak pliku wykresu {m.group(1)} (uruchom build.sh)")

    for m in re.finditer(r"\\begin\{(figure\*?|marginfigure)\}(.*?)\\end\{\1\}", text, re.S):
        body = m.group(2)
        line = text[:m.start()].count("\n") + 1
        if "\\caption" not in body and "\\sidecaption" not in body:
            issues.append(f"{path.name}:{line}: rysunek bez \\caption/\\sidecaption")
        if "\\label" not in body:
            issues.append(f"{path.name}:{line}: rysunek bez \\label")

    if path.name.startswith("rozdzial"):
        if "\\begin{intuicja}" not in text:
            issues.append(f"{path.name}: brak uwagi intuicja")
        if "\\begin{sprawdz}" not in text:
            issues.append(f"{path.name}: brak zadania sprawdz")

    return issues


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    root = Path(sys.argv[1])
    files = sorted(list(root.glob("rozdzial-*.tex")) + list(root.glob("dodatek-*.tex")))
    if not files:
        print("Nie znaleziono plików rozdzial-*.tex w", root)
        return 2
    all_issues = []
    for f in files:
        all_issues += check(f)
    if all_issues:
        print("BRAKI:")
        for i in all_issues:
            print(" -", i)
        return 1
    print(f"OK: {len(files)} plików bez braków")
    return 0


if __name__ == "__main__":
    sys.exit(main())
