#!/usr/bin/env bash
# Budowanie książki: build.sh <katalog-z-ksiazka.tex> [plik.tex]
# Wynik: PDF obok źródła, log w build.log, podgląd stron w podglad/strona-N.png
set -u
DIR="${1:?podaj katalog z książką}"
MAIN="${2:-ksiazka.tex}"
cd "$DIR" || exit 1

if ! command -v pdflatex >/dev/null 2>&1; then
  echo "Brak pdflatex. Zainstaluj: apt-get install -y texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-pictures texlive-lang-polish texlive-fonts-recommended lmodern poppler-utils" >&2
  exit 2
fi

# Wykresy powstają osobno w Pythonie (figures/gen_*.py -> figures/*.pdf), przed składem
if ls figures/gen_*.py >/dev/null 2>&1; then
  for g in figures/gen_*.py; do
    (cd figures && python3 "$(basename "$g")") || { echo "BŁĄD generowania wykresów: $g" >&2; exit 3; }
  done
fi

# latexmk sam wykona tyle przebiegów, ile trzeba (spis treści, odsyłacze, wykresy)
latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error "$MAIN" > build.log 2>&1
STATUS=$?

if [ $STATUS -ne 0 ]; then
  echo "BŁĄD KOMPILACJI. Pierwsze błędy:"
  grep -n -m 8 -A 3 -E '^\S+:[0-9]+:|^!' build.log
  exit $STATUS
fi

echo "Ostrzeżenia (nierozwiązane odsyłacze, przepełnione ramki):"
# czytamy log ostatniego przebiegu (build.log zawiera też pierwsze przebiegi z odsyłaczami jeszcze nieznanymi)
grep -E "undefined|Overfull \\\\hbox \([0-9]{2,}" "${MAIN%.tex}.log" | sort | uniq -c | head -20

PDF="${MAIN%.tex}.pdf"
PAGES=$(pdfinfo "$PDF" 2>/dev/null | awk '/^Pages:/{print $2}')
echo "OK: $PDF (${PAGES:-?} stron)"

if command -v pdftoppm >/dev/null 2>&1; then
  mkdir -p podglad && rm -f podglad/strona-*.png
  pdftoppm -r 60 -png "$PDF" podglad/strona
  echo "Podgląd stron: $DIR/podglad/"
fi
