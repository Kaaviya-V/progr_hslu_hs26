"""Berechnen: Mengen und Kosten je Position.

Die Mengenart der Position bestimmt, welche Menge des Bauteils zaehlt
(z.B. Fläche -> Spalte flaeche). Menge je Position = Summe der Bauteile,
Kosten = Menge x Einheitspreis, Total exkl. MwSt.
Fehlende Preise und Mengen werden nicht still mit 0 gerechnet, sondern als Hinweis ausgewiesen.
"""

import pandas as pd

from calculation.mapping import MELDUNG_SPALTEN
from validation.model_checks import HINWEIS

KOSTEN_SPALTEN = [
    "pos_id", "ebkp_code", "gruppe", "bezeichnung", "mengenart", "anzahl_bauteile",
    "menge", "einheit", "einheitspreis", "kosten", "anteil", "hinweis",
]


def _massgebende_menge(bauteil):
    """Holt beim Bauteil die Menge aus der Spalte, die zur Mengenart der Position passt."""
    spalte = bauteil["mengenspalte"]
    if pd.isna(spalte):
        return None
    return bauteil[spalte]


def berechne_bauteilkosten(bauteile, positionen):
    """Ergaenzt jedes zugeordnete Bauteil um menge, einheit, einheitspreis und kosten.

    So bleibt jede Zahl ueber die GUID auf das Bauteil zurueckfuehrbar.
    Bauteile ohne Pos-ID behalten leere Werte.
    """
    preise = positionen[["pos_id", "mengenspalte", "einheit", "einheitspreis"]]
    bauteile = bauteile.merge(preise, on="pos_id", how="left")
    bauteile["menge"] = pd.to_numeric(bauteile.apply(_massgebende_menge, axis=1), errors="coerce")
    bauteile["kosten"] = bauteile["menge"] * bauteile["einheitspreis"]
    return bauteile


def _hinweis_position(position):
    """Text fuer die Spalte hinweis in der Kostentabelle."""
    hinweise = []
    if position["anzahl_bauteile"] == 0:
        hinweise.append("kein Bauteil im Modell")
    elif position["menge"] == 0:
        hinweise.append("Menge 0 – im Modell fehlt die Menge")
    if pd.isna(position["einheitspreis"]):
        hinweise.append("ohne Preis")
    return "; ".join(hinweise) or None


def berechne_positionen(bauteile, positionen):
    """Fasst die Bauteile je Pos-ID zusammen: Anzahl, Menge, Kosten, Anteil am Total.

    bauteile muss schon durch berechne_bauteilkosten gegangen sein.
    Alle Positionen der Liste erscheinen, auch die ohne Bauteil (Anzahl 0).
    """
    summen = bauteile.dropna(subset=["pos_id"]).groupby("pos_id").agg(
        anzahl_bauteile=("guid", "count"),
        menge=("menge", "sum"),          # fehlende Mengen zaehlen hier als 0, der Hinweis zeigt es an
    )
    kosten = positionen.merge(summen, on="pos_id", how="left")
    kosten["anzahl_bauteile"] = kosten["anzahl_bauteile"].fillna(0).astype(int)
    kosten["menge"] = kosten["menge"].fillna(0.0)
    kosten["kosten"] = kosten["menge"] * kosten["einheitspreis"]   # ohne Preis -> leer, nicht 0
    kosten["anteil"] = kosten["kosten"] / berechne_total(kosten)
    kosten["hinweis"] = kosten.apply(_hinweis_position, axis=1)
    return kosten[KOSTEN_SPALTEN]


def berechne_total(kosten):
    """Total exkl. MwSt. (Positionen ohne Preis zaehlen nicht mit)."""
    return kosten["kosten"].sum()


def melde_fehlende_mengen(bauteile):
    """Hinweis fuer jedes zugeordnete Bauteil, das fuer seine Mengenart keine Menge > 0 hat."""
    meldungen = []
    zugeordnet = bauteile.dropna(subset=["pos_id"])
    ohne_menge = zugeordnet[zugeordnet["menge"].isna() | (zugeordnet["menge"] == 0)]
    for _, bauteil in ohne_menge.iterrows():
        text = (f"{bauteil['klasse']} «{bauteil['name']}»: keine {bauteil['mengenspalte']} "
                f"im Modell, Position {bauteil['pos_id']} rechnet mit Menge 0")
        meldungen.append({
            "schwere": HINWEIS,
            "pruefung": "Menge fehlt",
            "guid": bauteil["guid"],
            "fachmodell": bauteil["fachmodell"],
            "pos_id": bauteil["pos_id"],
            "meldung": text,
        })
    return pd.DataFrame(meldungen, columns=MELDUNG_SPALTEN)


def berechne_kosten(bauteile, positionen):
    """Ganzer Schritt 6 in einem Aufruf.

    Gibt (kosten, bauteile, meldungen) zurueck:
    kosten = eine Zeile pro Position, bauteile = mit menge und kosten je Bauteil,
    meldungen = Bauteile ohne Menge.
    """
    bauteile = berechne_bauteilkosten(bauteile, positionen)
    kosten = berechne_positionen(bauteile, positionen)
    meldungen = melde_fehlende_mengen(bauteile)
    return kosten, bauteile, meldungen


if __name__ == "__main__":
    # Test im Terminal: python -m calculation.costs
    from calculation.mapping import ordne_zu
    from importers.ebkp_reader import lese_ebkp_liste
    from importers.ifc_reader import lese_alle_ifc

    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 60)
    positionen, zuordnung, einstellungen = lese_ebkp_liste("daten/eBKP-T_Preisliste_Zuordnung.xlsx")
    bauteile = lese_alle_ifc("daten", einstellungen)
    bauteile, _ = ordne_zu(bauteile, zuordnung, positionen)

    kosten, bauteile, meldungen = berechne_kosten(bauteile, positionen)
    spalten = ["pos_id", "bezeichnung", "anzahl_bauteile", "menge", "einheit", "einheitspreis", "kosten", "hinweis"]
    print(kosten[kosten["pos_id"].isin(["P01", "P08", "P22", "P30", "P37"])][spalten].round(3).to_string())
    print(f"\nTotal exkl. MwSt.: CHF {berechne_total(kosten):,.2f}".replace(",", "'"), "(Soll: 896'542.43, exakt 896'542.12)")
    print("\nMeldungen:")
    print(meldungen.to_string())
