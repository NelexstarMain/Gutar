"""Styl wykresów książki wzorowany na „Mathematics for Machine Learning”.

Zasady stylu (tak wyglądają rysunki w MML):
  * BEZ napisów: żadnych tytułów, słów, wartości liczbowych ani legend na rysunku. Wolno
    tylko symbole matematyczne (np. u, v, e_1, h) oraz oznaczenia paneli (a), (b). Cały opis
    jest w \\sidecaption w LaTeX-u (podpis na marginesie).
  * Osie: cienkie czarne strzałki przez początek układu, bez ramki, siatki i podziałek.
  * Kolory: jasnoniebieskie wypełnienia z niebieskim konturem; drugi kolor (pomarańczowy)
    tylko tam, gdzie znaczenie jest przeciwne (np. orientacja odwrócona). Reszta czarna i szara.

Użycie w skrypcie rozdziału:
    from figstyle import *
    fig, ax = nowa_figura("tekst", 2.4)
    uklad_xy(ax, (-0.5, 3.5), (-0.5, 2.0))
    ...
    zapisz(fig, "obraz-kwadratu")   # -> figures/obraz-kwadratu.pdf (wektorowo)

Szerokości: "tekst" = szerokość tekstu książki, "margines" = szerokość marginesu,
"pelna" = tekst + margines (dla figure*). Czcionka: Times jak w książce (LaTeX/usetex, jeśli
działa; w przeciwnym razie TeX Gyre Termes lub STIX). FIGSTYLE_NOTEX=1 wyłącza LaTeX.
"""
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon

# ---------- paleta w stylu MML ----------
NIEBIESKI = "#1F5FAF"          # kontur, główne strzałki
JASNONIEBIESKI = "#A9D3EC"     # wypełnienia (orientacja dodatnia, zbiory)
POMARANCZ = "#E8892B"          # drugi wektor, kontur przeciwnego znaczenia
JASNOPOMARANCZ = "#F7CC9A"     # wypełnienie przeciwnego znaczenia (orientacja ujemna)
ZOLTY = "#F2C230"
FIOLET = "#7E6BB5"
CZARNY = "#111111"
SZARY = "#6B6B6B"

# ---------- szerokości w calach (zgodne z geometry w preambula.tex) ----------
CM = 1 / 2.54
SZEROKOSC = {"tekst": 11.6 * CM, "margines": 4.9 * CM, "pelna": (11.6 + 0.55 + 4.9) * CM}

KATALOG = Path(__file__).resolve().parent


def _usetex_dziala() -> bool:
    """Czy matplotlib potrafi złożyć tekst przez LaTeX (potrzebny latex, dvipng, cm-super)."""
    if os.environ.get("FIGSTYLE_NOTEX"):
        plt.rcParams.update({"text.usetex": False})
        return False
    try:
        plt.rcParams.update({"text.usetex": True})
        fig = plt.figure(figsize=(1, 1))
        fig.text(0.5, 0.5, r"$\theta$ ąę")
        fig.canvas.draw()
        plt.close(fig)
        return True
    except Exception:
        plt.rcParams.update({"text.usetex": False})
        return False


def ustaw_styl() -> str:
    plt.rcParams.update({
        "font.size": 9, "axes.labelsize": 9, "legend.frameon": False,
        "axes.linewidth": 0.6, "lines.linewidth": 1.3,
        "figure.dpi": 150, "savefig.dpi": 300,
        "pdf.fonttype": 42,  # czcionki osadzone, tekst zaznaczalny
    })
    plt.rcParams["text.latex.preamble"] = (
        r"\usepackage[T1]{fontenc}\usepackage[utf8]{inputenc}\usepackage{mathptmx}\usepackage{bm}"
        r"\newcommand{\vect}[1]{\bm{#1}}"
    )
    plt.rcParams["font.family"] = "serif"
    if _usetex_dziala():
        return "usetex"
    from matplotlib import font_manager
    nazwy = {f.name for f in font_manager.fontManager.ttflist}
    if "TeX Gyre Termes" in nazwy:
        plt.rcParams.update({"font.serif": ["TeX Gyre Termes"], "mathtext.fontset": "custom",
                             "mathtext.rm": "TeX Gyre Termes", "mathtext.it": "TeX Gyre Termes:italic",
                             "mathtext.bf": "TeX Gyre Termes:bold", "mathtext.fallback": "stix"})
    else:
        plt.rcParams.update({"font.serif": ["STIXGeneral"], "mathtext.fontset": "stix"})
    return "mathtext"


TRYB = ustaw_styl()


def wek(symbol: str) -> str:
    """Wektor pogrubiony kursywą jak \\vect w książce (\\bm w LaTeX-u, \\mathbf w trybie awaryjnym)."""
    return rf"\vect{{{symbol}}}" if TRYB == "usetex" else rf"\mathbf{{{symbol}}}"


def nowa_figura(szer="tekst", wys=3.0, **kw):
    """Figura o szerokości z książki. szer: 'tekst' | 'margines' | 'pelna' | liczba w calach."""
    w = SZEROKOSC[szer] if isinstance(szer, str) else szer
    return plt.subplots(figsize=(w, wys), **kw)


def zapisz(fig, nazwa: str, katalog: Path | None = None):
    """Zapisuje PDF (wektorowy) do figures/<nazwa>.pdf."""
    katalog = katalog or KATALOG
    sciezka = katalog / f"{nazwa}.pdf"
    fig.savefig(sciezka, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    print("zapisano", sciezka.name)
    return sciezka


# ---------- pomocnicze rysowanie ----------
def os_strzalka(ax, p, q, lw=0.8, kolor=CZARNY):
    ax.annotate("", xy=q, xytext=p, zorder=1,
                arrowprops=dict(arrowstyle="-|>", color=kolor, lw=lw, shrinkA=0, shrinkB=0,
                                mutation_scale=8))


def uklad_xy(ax, xlim, ylim, rownaskala=True, osie=True):
    """Układ współrzędnych w stylu MML: czarne strzałki osi przez zero, bez ramki, siatki i liczb."""
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    if rownaskala:
        ax.set_aspect("equal")
    ax.set_axis_off()
    if osie:
        os_strzalka(ax, (xlim[0], 0), (xlim[1], 0))
        os_strzalka(ax, (0, ylim[0]), (0, ylim[1]))


def strzalka(ax, p, q, kolor=NIEBIESKI, lw=1.5, zorder=5, **kw):
    ax.annotate("", xy=q, xytext=p, zorder=zorder,
                arrowprops=dict(arrowstyle="-|>", color=kolor, lw=lw, shrinkA=0, shrinkB=0,
                                mutation_scale=10, **kw))


def wielokat(ax, pts, wypelnienie=JASNONIEBIESKI, kontur=NIEBIESKI, lw=1.0, zorder=2, **kw):
    ax.add_patch(Polygon(np.asarray(pts, float), closed=True, facecolor=wypelnienie,
                         edgecolor=kontur, lw=lw, zorder=zorder, **kw))


def rownoleglobok(ax, u, v, wypelnienie=JASNONIEBIESKI, kontur=NIEBIESKI, o=(0.0, 0.0), zorder=2, **kw):
    """Równoległobok rozpięty przez u i v z początkiem w o (jasne wypełnienie, ciemny kontur)."""
    o = np.asarray(o, float)
    u, v = np.asarray(u, float), np.asarray(v, float)
    pts = [o, o + u, o + u + v, o + v]
    wielokat(ax, pts, wypelnienie, kontur, zorder=zorder, **kw)
    return pts


def etykieta(ax, xy, tekst, kolor=CZARNY, dx=0, dy=0, **kw):
    """Symbol matematyczny przy punkcie (przesunięcie dx, dy w punktach). Tylko symbole, bez słów."""
    ax.annotate(tekst, xy=xy, xytext=(dx, dy), textcoords="offset points", color=kolor,
                ha=kw.pop("ha", "center"), va=kw.pop("va", "center"), fontsize=kw.pop("fontsize", 9), **kw)


def panel(ax, litera):
    """Oznaczenie panelu pod rysunkiem: (a), (b)... Opis panelu jest w podpisie na marginesie."""
    ax.text(0.5, -0.02, f"({litera})", transform=ax.transAxes, ha="center", va="top", fontsize=8.5)


def prosty_kat(ax, wierzcholek, kier1, kier2, rozmiar=0.12, kolor=CZARNY):
    """Mały kwadracik kąta prostego między kierunkami kier1 i kier2 (wektory jednostkowe)."""
    w = np.asarray(wierzcholek, float)
    a, b = np.asarray(kier1, float) * rozmiar, np.asarray(kier2, float) * rozmiar
    ax.plot(*zip(w + a, w + a + b, w + b), color=kolor, lw=0.7, zorder=6)
