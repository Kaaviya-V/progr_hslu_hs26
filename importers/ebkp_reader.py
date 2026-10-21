"""eBKP-T-Liste lesen: Blaetter Positionen, Zuordnung und Einstellungen.

Alle Blaetter haben den Titel in Zeile 1-2, die Spaltenkoepfe in Zeile 4
und die Daten ab Zeile 5. Die Spalten werden auf einheitliche, neutrale Namen
umbenannt, damit der Rest des Programms nicht von der Excel-Beschriftung abhaengt.
Geprueft wird hier noch nichts, das macht validation/list_checks.py.
"""

import pandas as pd

KOPFZEILE = 3          # pandas zaehlt ab 0: Zeile 4 in Excel
ERSTE_DATENZEILE = 5   # Excel-Zeilennummer der ersten Datenzeile

# Excel-Spaltenkopf -> neutraler Spaltenname
SPALTEN_POSITIONEN = {
    "Pos-ID": "pos_id",
    "eBKP-T Code": "ebkp_code",
    "Gruppe": "gruppe",
    "Bezeichnung": "bezeichnung",
    "Mengenart": "mengenart",
    "Einheit": "einheit",
    "Einheitspreis (CHF/Einheit)": "einheitspreis",
    "Bemerkung": "bemerkung",
}

SPALTEN_ZUORDNUNG = {
    "Pos-ID": "pos_id",
    "Bezeichnung (Info)": "bezeichnung",
    "IFC-Klasse": "ifc_klasse",
    "Bereich (Stufe_4)": "bereich",
    "Bauteilgruppe (Stufe_5)": "bauteilgruppe",
    "Typ / Schicht (Stufe_6)": "typ_schicht",
    "Element (Stufe_7)": "element",
    "Vergleich": "vergleich",
    "Bemerkung": "bemerkung",
}

# Mengenart (Text in der Liste) -> Mengenspalte in der Bauteiltabelle
MENGENARTEN = {
    "stück": "anzahl",
    "länge": "laenge",
    "fläche": "flaeche",
    "volumen": "volumen",
}

# Feld im Blatt «Einstellungen» -> (Gruppe, neutrales Feld) wie in ifc_reader
FELDER_EINSTELLUNGEN = {
    "bereich": ("felder", "bereich"),
    "bauteilgruppe": ("felder", "bauteilgruppe"),
    "typ / schicht": ("felder", "typ_schicht"),
    "element": ("felder", "element"),
    "stück": ("mengen", "anzahl"),
    "länge": ("mengen", "laenge"),
    "fläche": ("mengen", "flaeche"),
    "volumen": ("mengen", "volumen"),
}


def _bereinige(wert):
    """Entfernt Leerzeichen am Rand und doppelte Leerzeichen; leere Texte werden zu None."""
    if isinstance(wert, str):
        wert = " ".join(wert.split())
        if wert == "":
            return None
    return wert


def _schluessel(text):
    """Text als Vergleichsschluessel: bereinigt und klein geschrieben."""
    text = _bereinige(text)
    return text.lower() if isinstance(text, str) else None


def _lese_blatt(pfad, blatt, spalten):
    """Liest ein Blatt, benennt die Spalten um und entfernt leere Zeilen.

    Die Spalte excel_zeile merkt sich die Zeilennummer in Excel,
    damit Meldungen spaeter sagen koennen, wo der Fehler steht.
    """
    tabelle = pd.read_excel(pfad, sheet_name=blatt, header=KOPFZEILE)
    tabelle.columns = [_bereinige(str(spalte)) for spalte in tabelle.columns]
    tabelle = tabelle.rename(columns=spalten)
    tabelle = tabelle.map(_bereinige)
    tabelle["excel_zeile"] = tabelle.index + ERSTE_DATENZEILE
    datenspalten = [s for s in tabelle.columns if s != "excel_zeile"]
    tabelle = tabelle.dropna(how="all", subset=datenspalten).reset_index(drop=True)
    return tabelle


def lese_positionen(pfad):
    """Blatt «Positionen»: eine Zeile pro Pos-ID mit Mengenart und Einheitspreis.

    Zusaetzlich die Spalte mengenspalte: welche Menge des Bauteils zaehlt
    (anzahl, laenge, flaeche, volumen; leer, wenn die Mengenart unbekannt ist).
    """
    positionen = _lese_blatt(pfad, "Positionen", SPALTEN_POSITIONEN)
    if "mengenart" in positionen.columns:
        positionen["mengenspalte"] = positionen["mengenart"].map(lambda m: MENGENARTEN.get(_schluessel(m)))
    return positionen


def lese_zuordnung(pfad):
    """Blatt «Zuordnung»: eine Zeile pro Regel. Leere Filter bleiben None (= egal)."""
    zuordnung = _lese_blatt(pfad, "Zuordnung", SPALTEN_ZUORDNUNG)
    if "vergleich" in zuordnung.columns:
        zuordnung["vergleich"] = zuordnung["vergleich"].map(_schluessel)
    return zuordnung


def lese_einstellungen(pfad):
    """Blatt «Einstellungen»: gibt ein Dictionary im Format von EINSTELLUNGEN_STANDARD zurueck.

    {"felder": {"bereich": ("GoBau_Struktur", "Stufe_4"), ...},
     "mengen": {"anzahl": ("GoBau_Menge", "Anzahl (Stk.)"), ...}}
    Zeilen mit unbekanntem Feld (z.B. die Notiz unter der Tabelle) werden uebersprungen.
    """
    tabelle = pd.read_excel(pfad, sheet_name="Einstellungen", header=KOPFZEILE)
    tabelle.columns = [_bereinige(str(spalte)) for spalte in tabelle.columns]

    einstellungen = {"felder": {}, "mengen": {}}
    for _, zeile in tabelle.iterrows():
        eintrag = FELDER_EINSTELLUNGEN.get(_schluessel(zeile["Feld"]))
        if eintrag is None:
            continue
        gruppe, feld = eintrag
        einstellungen[gruppe][feld] = (_bereinige(zeile["Property-Set"]), _bereinige(zeile["Property-Name"]))
    return einstellungen


def lese_ebkp_liste(pfad):
    """Liest alle drei Blaetter und gibt (positionen, zuordnung, einstellungen) zurueck."""
    return lese_positionen(pfad), lese_zuordnung(pfad), lese_einstellungen(pfad)


if __name__ == "__main__":
    # Test im Terminal: python -m importers.ebkp_reader
    from importers.ifc_reader import EINSTELLUNGEN_STANDARD

    pd.set_option("display.width", 200)
    positionen, zuordnung, einstellungen = lese_ebkp_liste("daten/eBKP-T_Preisliste_Zuordnung.xlsx")

    print("Positionen:", len(positionen), "(Soll: 95)")
    print(positionen.head(3).to_string())
    print("Mengenarten:", positionen["mengenspalte"].value_counts().to_dict())

    print("\nRegeln:", len(zuordnung), "(Soll: 103)")
    print(zuordnung.head(3).to_string())
    print("Vergleich:", zuordnung["vergleich"].value_counts().to_dict())

    print("\nEinstellungen:")
    for gruppe, felder in einstellungen.items():
        for feld, quelle in felder.items():
            print(f"  {feld:15} {quelle}")
    print("Gleich wie EINSTELLUNGEN_STANDARD:", einstellungen == EINSTELLUNGEN_STANDARD, "(Soll: True)")
