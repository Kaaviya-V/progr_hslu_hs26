"""Zuordnen: Regeln aus dem Blatt «Zuordnung» auf die Bauteile anwenden.

Eine Regel passt, wenn ALLE ausgefuellten Filter passen (leerer Filter = egal).
- IFC-Klasse: immer exakt gleich
- Bereich, Bauteilgruppe, Typ/Schicht, Element: je nach Spalte «Vergleich»
  «gleich» = bereinigter Text identisch, «enthält» = Filtertext kommt im Wert vor
Jedes Bauteil muss genau EINE Pos-ID treffen. Mehrere Regeln derselben Pos-ID zaehlen als eine.

Meldungen (gleiches Format wie model_checks, zusaetzlich pos_id):
- Bauteil ohne Position -> Hinweis (wird «ohne Preis» ausgewiesen)
- Bauteil mit mehreren Positionen -> Fehler (Konflikt), mit Angabe der Regeln
- Position ohne Bauteil -> Hinweis
"""

import pandas as pd

from validation.model_checks import FEHLER, HINWEIS

MELDUNG_SPALTEN = ["schwere", "pruefung", "guid", "fachmodell", "pos_id", "meldung"]

# Filter, die mit «gleich» oder «enthält» verglichen werden (Spaltenname in Regel = in Bauteil)
TEXTFILTER = ["bereich", "bauteilgruppe", "typ_schicht", "element"]


def bereinige_text(text):
    """Fuer Vergleiche: Leerzeichen am Rand und doppelte weg, alles klein. Leer -> None."""
    if not isinstance(text, str):
        return None
    text = " ".join(text.split()).lower()
    return text or None


def _text_passt(wert, filtertext, vergleich):
    """Vergleicht einen Bauteilwert mit einem Filtertext (beide schon bereinigt)."""
    if wert is None:
        return False
    if vergleich == "gleich":
        return wert == filtertext
    return filtertext in wert   # «enthält»


def regel_passt(bauteil, regel):
    """True, wenn alle ausgefuellten Filter der Regel auf das Bauteil passen.

    bauteil und regel sind Dictionaries mit bereits bereinigten Texten.
    """
    if regel["ifc_klasse"] is not None and regel["ifc_klasse"] != bauteil["klasse"]:
        return False
    for feld in TEXTFILTER:
        filtertext = regel[feld]
        if filtertext is not None and not _text_passt(bauteil[feld], filtertext, regel["vergleich"]):
            return False
    return True


def _bereite_regeln_vor(zuordnung):
    """Wandelt die Regeltabelle in eine Liste von Dictionaries mit bereinigten Texten um.

    Das Bereinigen passiert so nur einmal pro Regel statt einmal pro Bauteil und Regel.
    """
    regeln = []
    for _, zeile in zuordnung.iterrows():
        regel = {
            "pos_id": zeile["pos_id"],
            "excel_zeile": zeile["excel_zeile"],
            "ifc_klasse": zeile["ifc_klasse"].strip() if isinstance(zeile["ifc_klasse"], str) else None,
            "vergleich": zeile["vergleich"],
        }
        for feld in TEXTFILTER:
            regel[feld] = bereinige_text(zeile[feld])
        regeln.append(regel)
    return regeln


def _meldung(schwere, pruefung, bauteil, pos_id, text):
    """Baut eine Meldungszeile; bauteil kann None sein (bei «Position ohne Bauteil»)."""
    return {
        "schwere": schwere,
        "pruefung": pruefung,
        "guid": None if bauteil is None else bauteil["guid"],
        "fachmodell": None if bauteil is None else bauteil["fachmodell"],
        "pos_id": pos_id,
        "meldung": text,
    }


def ordne_zu(bauteile, zuordnung, positionen):
    """Wendet alle Regeln auf alle Bauteile an.

    Gibt (bauteile, meldungen) zurueck. Die Bauteiltabelle bekommt drei neue Spalten:
    - pos_id:          die gefundene Pos-ID (leer bei keiner oder mehreren)
    - treffer_pos_ids: alle getroffenen Pos-IDs, z.B. «P05, P07» (fuer die Kontrolle)
    - treffer_regeln:  Excel-Zeilen der getroffenen Regeln, z.B. «9, 10»
    """
    regeln = _bereite_regeln_vor(zuordnung)
    bauteile = bauteile.copy()
    meldungen = []
    spalte_pos_id, spalte_pos_ids, spalte_regeln = [], [], []

    for _, zeile in bauteile.iterrows():
        bauteil = {"klasse": zeile["klasse"]}
        for feld in TEXTFILTER:
            bauteil[feld] = bereinige_text(zeile[feld])

        treffer = [regel for regel in regeln if regel_passt(bauteil, regel)]
        pos_ids = sorted({regel["pos_id"] for regel in treffer})   # set: gleiche Pos-ID nur einmal
        regel_zeilen = ", ".join(str(regel["excel_zeile"]) for regel in treffer)

        name = f"{zeile['klasse']} «{zeile['name']}»"
        if len(pos_ids) == 0:
            text = f"{name}: keine Regel passt, Bauteil wird ohne Preis ausgewiesen"
            meldungen.append(_meldung(HINWEIS, "Ohne Position", zeile, None, text))
        elif len(pos_ids) > 1:
            text = f"{name}: passt auf {', '.join(pos_ids)} (Regeln in Zeilen {regel_zeilen})"
            meldungen.append(_meldung(FEHLER, "Konflikt", zeile, ", ".join(pos_ids), text))

        spalte_pos_id.append(pos_ids[0] if len(pos_ids) == 1 else None)
        spalte_pos_ids.append(", ".join(pos_ids) or None)
        spalte_regeln.append(regel_zeilen or None)

    bauteile["pos_id"] = spalte_pos_id
    bauteile["treffer_pos_ids"] = spalte_pos_ids
    bauteile["treffer_regeln"] = spalte_regeln

    # Positionen, die kein einziges Bauteil getroffen haben
    getroffen = set(bauteile["pos_id"].dropna())
    for _, position in positionen.iterrows():
        if position["pos_id"] not in getroffen:
            text = f"Position {position['pos_id']} «{position['bezeichnung']}» hat kein Bauteil im Modell"
            meldungen.append(_meldung(HINWEIS, "Position ohne Bauteil", None, position["pos_id"], text))

    return bauteile, pd.DataFrame(meldungen, columns=MELDUNG_SPALTEN)


if __name__ == "__main__":
    # Test im Terminal: python -m calculation.mapping
    from importers.ebkp_reader import lese_ebkp_liste
    from importers.ifc_reader import lese_alle_ifc

    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 100)
    liste = "daten/eBKP-T_Preisliste_Zuordnung.xlsx"
    positionen, zuordnung, einstellungen = lese_ebkp_liste(liste)
    bauteile = lese_alle_ifc("daten", einstellungen)

    print("=== Test 1: alle 9 Modelle ===")
    zugeordnet, meldungen = ordne_zu(bauteile, zuordnung, positionen)
    print("Bauteile:", len(zugeordnet), "(Soll: 852)")
    print("mit genau einer Position:", zugeordnet["pos_id"].notna().sum(), "(Soll: 852)")
    print(meldungen.groupby(["schwere", "pruefung"]).size().to_string() if len(meldungen) else "keine Meldungen (Soll)")

    # Vergleich mit dem Blatt «Kontrolle»: Anzahl Bauteile je Pos-ID
    kontrolle = pd.read_excel(liste, sheet_name="Kontrolle", header=3).dropna(subset=["Pos-ID"])
    soll = kontrolle.set_index("Pos-ID")["Anzahl Bauteile"].fillna(0).astype(int)
    ist = zugeordnet.groupby("pos_id").size().reindex(soll.index, fill_value=0)
    abweichungen = pd.DataFrame({"soll": soll, "ist": ist})
    abweichungen = abweichungen[abweichungen["soll"] != abweichungen["ist"]]
    print("Pos-IDs mit anderer Anzahl Bauteile als im Blatt Kontrolle:", len(abweichungen), "(Soll: 0)")
    if len(abweichungen):
        print(abweichungen.to_string())

    print("\n=== Test 2: Regel absichtlich zu breit (Konflikt) und Regel geloescht (ohne Position) ===")
    zuo = zuordnung.copy()
    zuo.loc[0, ["typ_schicht", "vergleich"]] = ["AC 8", "enthält"]   # P01 trifft jetzt auch P02/P05
    zuo = zuo[zuo["pos_id"] != "P90"]                                  # Hecken haben keine Regel mehr
    _, meldungen = ordne_zu(bauteile, zuo, positionen)
    print(meldungen.groupby(["schwere", "pruefung"]).size().to_string())
    print(meldungen.groupby("pruefung").head(2).to_string())
