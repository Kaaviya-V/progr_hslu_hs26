"""Diagramm Version 1 (Matplotlib, eingefroren fuer Z_main_v1.py). Aktuell: visualization/charts.py (Plotly).

Gestaltung: eine Farbe (nur eine Datenreihe, darum keine Legende), Balken nach Kosten
sortiert (groesste oben), Betrag und Anteil direkt am Balkenende, Raster und Achsen zurueckhaltend.
Waagrechte Balken, weil die Gruppennamen lang sind und so lesbar bleiben.
"""

from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

BALKEN_FARBE = "#2a78d6"
HINTERGRUND = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_LEISE = "#52514e"
RASTER = "#e4e3df"


def chf(betrag):
    """Betrag mit Schweizer Tausendertrennzeichen, ohne Rappen: 123456.7 -> 123'457."""
    return f"{betrag:,.0f}".replace(",", "'")


def kosten_je_gruppe(kosten):
    """Summiert die Kosten der Positionen je Gruppe, groesste zuerst.

    Positionen ohne Preis (Kosten leer) zaehlen nicht mit.
    """
    return kosten.groupby("gruppe")["kosten"].sum().sort_values(ascending=False)


def diagramm_kosten_je_gruppe(kosten):
    """Zeichnet das Balkendiagramm und gibt die Matplotlib-Figur zurueck."""
    summen = kosten_je_gruppe(kosten)
    total = summen.sum()

    hoehe = 0.9 + 0.32 * len(summen)          # Figur waechst mit der Anzahl Gruppen
    # Figure direkt statt plt.subplots: Matplotlib merkt sich die Figur nicht, so fuellt
    # sich der Speicher nicht, wenn Streamlit das Skript bei jedem Klick neu ausfuehrt
    fig = Figure(figsize=(9, hoehe), facecolor=HINTERGRUND)
    ax = fig.subplots()
    ax.set_facecolor(HINTERGRUND)

    # Groesste Gruppe oben: barh zeichnet von unten nach oben, darum umdrehen
    gruppen = summen.index[::-1]
    werte = summen.values[::-1]
    ax.barh(gruppen, werte, height=0.62, color=BALKEN_FARBE)

    # Betrag und Anteil direkt am Balkenende (Text in Textfarbe, nicht in Balkenfarbe)
    for y, wert in enumerate(werte):
        anteil = wert / total
        anteil_text = "<1%" if anteil < 0.005 else f"{anteil:.0%}"
        ax.text(wert + total * 0.002, y, f"{chf(wert)}  ({anteil_text})",
                va="center", fontsize=8.5, color=TEXT_LEISE)

    # Zurueckhaltende Achsen: nur senkrechte Rasterlinien, keine Rahmenlinien
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x / 1000:.0f}k"))
    ax.grid(axis="x", color=RASTER, linewidth=0.8)
    ax.set_axisbelow(True)
    for seite in ["top", "right", "left", "bottom"]:
        ax.spines[seite].set_visible(False)
    ax.tick_params(axis="both", length=0, labelsize=9, colors=TEXT_LEISE)
    ax.tick_params(axis="y", colors=TEXT)
    ax.set_xlim(0, summen.max() * 1.22)      # Platz fuer die Beschriftung rechts
    ax.margins(y=0.01)

    ax.set_title(f"Kosten je Gruppe – Total CHF {chf(total)} exkl. MwSt.",
                 loc="left", fontsize=11, color=TEXT, pad=10)
    ax.set_xlabel("CHF", fontsize=9, color=TEXT_LEISE, loc="right")
    fig.tight_layout()
    return fig


if __name__ == "__main__":
    # Test im Terminal: python -m visualization.charts  -> speichert daten/diagramm_test.png
    from calculation.costs import berechne_kosten
    from calculation.mapping import ordne_zu
    from importers.ebkp_reader import lese_ebkp_liste
    from importers.ifc_reader import lese_alle_ifc

    positionen, zuordnung, einstellungen = lese_ebkp_liste("daten/eBKP-T_Preisliste_Zuordnung.xlsx")
    bauteile, _ = ordne_zu(lese_alle_ifc("daten", einstellungen), zuordnung, positionen)
    kosten, _, _ = berechne_kosten(bauteile, positionen)

    summen = kosten_je_gruppe(kosten)
    print(summen.round(2).to_string())
    print("Summe der Gruppen:", chf(summen.sum()), "(Soll: 896'542)")
    diagramm_kosten_je_gruppe(kosten).savefig("daten/diagramm_test.png", dpi=130)
    print("Gespeichert: daten/diagramm_test.png")
