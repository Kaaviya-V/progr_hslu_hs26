"""Modell pruefen: Pflichtangaben, Mengen und Duplikate.

Ergebnis ist eine Tabelle mit einer Zeile pro Meldung:
schwere (Fehler/Hinweis), pruefung, guid, fachmodell, meldung.
Fehler sperren das Weiterfahren, Hinweise nicht.
"""

import pandas as pd

FEHLER = "Fehler"
HINWEIS = "Hinweis"

MELDUNG_SPALTEN = ["schwere", "pruefung", "guid", "fachmodell", "meldung"]

# Pflichtangaben je IFC-Klasse: Feld -> Schwere, wenn es fehlt
PFLICHTFELDER = {
    "IfcCourse": {"bereich": FEHLER, "bauteilgruppe": FEHLER, "typ_schicht": FEHLER},
    "IfcEarthworksFill": {"bereich": FEHLER, "bauteilgruppe": FEHLER, "typ_schicht": FEHLER},
    "IfcKerb": {"bereich": FEHLER, "bauteilgruppe": FEHLER, "typ_schicht": FEHLER, "element": HINWEIS},
    "IfcBuiltElement": {"bereich": FEHLER, "bauteilgruppe": FEHLER, "typ_schicht": FEHLER, "element": HINWEIS},
}

MENGEN = ["anzahl", "laenge", "flaeche", "volumen"]


def _meldung(schwere, pruefung, bauteil, text):
    """Baut eine Meldungszeile fuer ein Bauteil (eine Zeile der Bauteiltabelle)."""
    return {
        "schwere": schwere,
        "pruefung": pruefung,
        "guid": bauteil["guid"],
        "fachmodell": bauteil["fachmodell"],
        "meldung": text,
    }


def _bereinige_text(text):
    """Fuer Vergleiche: Leerzeichen am Rand und doppelte weg, alles klein."""
    if not isinstance(text, str):
        return text
    return " ".join(text.split()).lower()


def pruefe_pflichtangaben(bauteile):
    """Meldet fehlende Pflichtfelder je nach IFC-Klasse."""
    meldungen = []
    for _, bauteil in bauteile.iterrows():
        pflicht = PFLICHTFELDER.get(bauteil["klasse"], {})
        for feld, schwere in pflicht.items():
            if pd.isna(bauteil[feld]):
                text = f"{bauteil['klasse']} «{bauteil['name']}»: Angabe «{feld}» fehlt"
                meldungen.append(_meldung(schwere, "Pflichtangabe", bauteil, text))
    return meldungen


def pruefe_mengen(bauteile):
    """Meldet Bauteile, bei denen keine der vier Mengen groesser als 0 ist.

    Bei Klassen mit Pflichtangaben ist das ein Fehler, sonst ein Hinweis.
    """
    meldungen = []
    for _, bauteil in bauteile.iterrows():
        hat_menge = any(pd.notna(bauteil[m]) and bauteil[m] > 0 for m in MENGEN)
        if not hat_menge:
            schwere = FEHLER if bauteil["klasse"] in PFLICHTFELDER else HINWEIS
            text = f"{bauteil['klasse']} «{bauteil['name']}»: keine Menge grösser als 0"
            meldungen.append(_meldung(schwere, "Menge", bauteil, text))
    return meldungen


def pruefe_doppelte_guid(bauteile):
    """Meldet GUIDs, die mehr als einmal vorkommen (Fehler)."""
    meldungen = []
    doppelt = bauteile[bauteile["guid"].duplicated(keep=False)]
    for guid, gruppe in doppelt.groupby("guid"):
        modelle = ", ".join(gruppe["fachmodell"])
        for _, bauteil in gruppe.iterrows():
            text = f"GUID kommt {len(gruppe)}x vor (in {modelle})"
            meldungen.append(_meldung(FEHLER, "Doppelte GUID", bauteil, text))
    return meldungen


def pruefe_gleiche_bauteile(bauteile):
    """Meldet Bauteile mit gleicher Klasse, Bezeichnung und Begrenzungsbox (Hinweis).

    Gleiche Namen allein sind kein Problem; erst die gleiche Lage deutet auf ein Duplikat.
    """
    meldungen = []
    if "begrenzungsbox" not in bauteile.columns:
        return meldungen

    tabelle = bauteile.dropna(subset=["begrenzungsbox"]).copy()
    tabelle["name_bereinigt"] = tabelle["name"].map(_bereinige_text)
    schluessel = ["klasse", "name_bereinigt", "begrenzungsbox"]
    gleiche = tabelle[tabelle.duplicated(subset=schluessel, keep=False)]

    for _, gruppe in gleiche.groupby(schluessel):
        for _, bauteil in gruppe.iterrows():
            andere = [g for g in gruppe["guid"] if g != bauteil["guid"]]
            text = f"«{bauteil['name']}» liegt gleich wie {', '.join(andere)} (mögliches Duplikat)"
            meldungen.append(_meldung(HINWEIS, "Gleiches Bauteil", bauteil, text))
    return meldungen


def pruefe_modell(bauteile):
    """Fuehrt alle Pruefungen aus und gibt alle Meldungen als eine Tabelle zurueck."""
    meldungen = []
    meldungen += pruefe_pflichtangaben(bauteile)
    meldungen += pruefe_mengen(bauteile)
    meldungen += pruefe_doppelte_guid(bauteile)
    meldungen += pruefe_gleiche_bauteile(bauteile)
    return pd.DataFrame(meldungen, columns=MELDUNG_SPALTEN)


def hat_fehler(meldungen):
    """True, wenn mindestens eine Meldung ein Fehler ist (dann ist Weiterfahren gesperrt)."""
    return (meldungen["schwere"] == FEHLER).any()


if __name__ == "__main__":
    # Test im Terminal: python -m validation.model_checks
    from importers.ifc_reader import lese_alle_ifc

    bauteile = lese_alle_ifc("daten")

    print("=== Test 1: die 9 Originalmodelle ===")
    meldungen = pruefe_modell(bauteile)
    print(meldungen.groupby(["schwere", "pruefung"]).size().to_string())
    print("Fehler vorhanden:", hat_fehler(meldungen), "(Soll: False)")

    print("\n=== Test 2: absichtlich veraenderte Kopie ===")
    kaputt = bauteile.copy()
    kurs = kaputt.index[kaputt["klasse"] == "IfcCourse"]
    kaputt.loc[kurs[0], "typ_schicht"] = None                    # leere Bezeichnung -> Fehler
    kaputt.loc[kurs[1], ["anzahl", "laenge", "flaeche", "volumen"]] = 0   # Menge 0 -> Fehler
    kaputt.loc[kurs[2], "guid"] = kaputt.loc[kurs[3], "guid"]     # doppelte GUID -> 2 Fehler
    kopie = kaputt.loc[[kurs[4]]].assign(guid="KOPIE_TEST")
    kaputt = pd.concat([kaputt, kopie], ignore_index=True)      # gleiches Bauteil -> 2 Hinweise

    meldungen = pruefe_modell(kaputt)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 80)
    print(meldungen[meldungen["pruefung"] != "Pflichtangabe"].to_string())
    print(meldungen[meldungen["schwere"] == FEHLER].to_string())
    print("Fehler vorhanden:", hat_fehler(meldungen), "(Soll: True)")
