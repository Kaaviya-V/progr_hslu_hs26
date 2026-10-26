"""Diagramme: Kosten je Gruppe als waagrechtes Balkendiagramm (Plotly).

Gestaltung: eine Farbe (nur eine Datenreihe, darum keine Legende), Balken nach Kosten
sortiert (groesste oben), «Betrag (Anteil)» direkt am Balkenende, transparenter Hintergrund
(passt sich dem dunklen Streamlit-Theme an). Plotly zeigt beim Darueberfahren zusaetzlich
einen Tooltip mit Gruppe, Betrag und Anteil.

Version 1 mit Matplotlib: visualization/Z_charts_v1.py
"""

import plotly.graph_objects as go

BALKEN_FARBE = "#3987e5"     # Blau, fuer dunklen Hintergrund geeignet
TEXT = "#E8EEF0"             # wie textColor im Theme
TEXT_LEISE = "#9AA8AD"
RASTER = "rgba(232, 238, 240, 0.08)"
HOEHE = 500


def chf(betrag):
    """Betrag mit Schweizer Tausendertrennzeichen, ohne Rappen: 123456.7 -> 123'457."""
    return f"{betrag:,.0f}".replace(",", "'")


def kosten_je_gruppe(kosten):
    """Summiert die Kosten der Positionen je Gruppe, groesste zuerst.

    Positionen ohne Preis (Kosten leer) zaehlen nicht mit.
    """
    return kosten.groupby("gruppe")["kosten"].sum().sort_values(ascending=False)


def diagramm_kosten_je_gruppe(kosten):
    """Zeichnet das Balkendiagramm und gibt die Plotly-Figur zurueck."""
    summen = kosten_je_gruppe(kosten)
    total = summen.sum()
    anteile = summen / total
    beschriftung = [f"{chf(wert)} ({'<1%' if anteil < 0.005 else f'{anteil:.0%}'})"
                    for wert, anteil in zip(summen, anteile)]

    fig = go.Figure(go.Bar(
        x=summen.values,
        y=summen.index,
        orientation="h",
        marker_color=BALKEN_FARBE,
        text=beschriftung,
        textposition="outside",
        textfont=dict(color=TEXT_LEISE, size=12),
        cliponaxis=False,                      # Beschriftung darf ueber den Rand hinaus
        customdata=anteile.values,
        hovertemplate="<b>%{y}</b><br>CHF %{x:,.0f}<br>%{customdata:.1%} vom Total<extra></extra>",
    ))
    fig.update_layout(
        height=HOEHE,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",         # transparent
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT),
        title=dict(text=f"Kosten je Gruppe – Total CHF {chf(total)} exkl. MwSt.", x=0, font=dict(size=15)),
        bargap=0.35,
        separators=".'",                       # Dezimalpunkt und Apostroph als Tausendertrenner
        hoverlabel=dict(bgcolor="#162024", font_color=TEXT),
    )
    # Groesste Gruppe oben; rechts 25 % Platz fuer die Beschriftung
    fig.update_yaxes(autorange="reversed", showgrid=False, ticks="", ticklabelstandoff=8)
    fig.update_xaxes(range=[0, summen.max() * 1.25], gridcolor=RASTER, zeroline=False,
                     tickfont=dict(color=TEXT_LEISE), ticksuffix="", tickformat="~s")
    return fig


if __name__ == "__main__":
    # Test im Terminal: python -m visualization.charts  -> speichert daten/diagramm_test.html
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
    diagramm_kosten_je_gruppe(kosten).write_html("daten/diagramm_test.html")
    print("Gespeichert: daten/diagramm_test.html")
