"""eBKP-T-Liste pruefen: Pflichtspalten, Pos-IDs, Mengenarten, Preise und Regeln.

Ergebnis ist eine Tabelle mit einer Zeile pro Meldung:
schwere (Fehler/Hinweis), pruefung, blatt, excel_zeile, pos_id, meldung.
Statt GUID und Fachmodell (wie in model_checks) steht hier, wo in der Excel-Liste
das Problem liegt. Fehler sperren das Weiterfahren, Hinweise nicht.
"""

import numbers

import pandas as pd

from importers.ebkp_reader import MENGENARTEN
from importers.ifc_reader import EINSTELLUNGEN_STANDARD
from validation.model_checks import FEHLER, HINWEIS, hat_fehler  # noqa: F401 (hat_fehler fuer main.py)

MELDUNG_SPALTEN = ["schwere", "pruefung", "blatt", "excel_zeile", "pos_id", "meldung"]

# Ohne diese Spalten kann das Programm nicht rechnen
PFLICHTSPALTEN = {
    "Positionen": ["pos_id", "bezeichnung", "mengenart", "einheitspreis"],
    "Zuordnung": ["pos_id", "ifc_klasse", "bereich", "bauteilgruppe", "typ_schicht", "element", "vergleich"],
}

FILTERSPALTEN = ["ifc_klasse", "bereich", "bauteilgruppe", "typ_schicht", "element"]
GUELTIGE_VERGLEICHE = ["gleich", "enthält"]


def _meldung(schwere, pruefung, blatt, zeile, text):
    """Baut eine Meldungszeile; zeile ist eine Zeile der Positionen oder der Zuordnung (oder None)."""
    return {
        "schwere": schwere,
        "pruefung": pruefung,
        "blatt": blatt,
        "excel_zeile": None if zeile is None else zeile["excel_zeile"],
        "pos_id": None if zeile is None else zeile.get("pos_id"),
        "meldung": text,
    }


def _fehlende_spalten(tabelle, blatt):
    """Gibt die Pflichtspalten zurueck, die im Blatt fehlen."""
    return [s for s in PFLICHTSPALTEN[blatt] if s not in tabelle.columns]


def pruefe_pflichtspalten(positionen, zuordnung):
    """Meldet fehlende Pflichtspalten (Fehler)."""
    meldungen = []
    for blatt, tabelle in [("Positionen", positionen), ("Zuordnung", zuordnung)]:
        for spalte in _fehlende_spalten(tabelle, blatt):
            text = f"Pflichtspalte «{spalte}» fehlt"
            meldungen.append(_meldung(FEHLER, "Pflichtspalte", blatt, None, text))
    return meldungen


def pruefe_pos_ids(positionen):
    """Meldet leere und doppelte Pos-IDs im Blatt Positionen (Fehler)."""
    meldungen = []
    for _, zeile in positionen[positionen["pos_id"].isna()].iterrows():
        text = f"Position «{zeile.get('bezeichnung')}» hat keine Pos-ID"
        meldungen.append(_meldung(FEHLER, "Pos-ID", "Positionen", zeile, text))

    mit_id = positionen.dropna(subset=["pos_id"])
    doppelt = mit_id[mit_id["pos_id"].duplicated(keep=False)]
    for pos_id, gruppe in doppelt.groupby("pos_id"):
        zeilen = ", ".join(str(z) for z in gruppe["excel_zeile"])
        for _, zeile in gruppe.iterrows():
            text = f"Pos-ID {pos_id} kommt {len(gruppe)}x vor (Zeilen {zeilen})"
            meldungen.append(_meldung(FEHLER, "Doppelte Pos-ID", "Positionen", zeile, text))
    return meldungen


def pruefe_mengenarten(positionen):
    """Meldet Positionen ohne gueltige Mengenart (Fehler), sonst weiss man nicht, welche Menge zaehlt."""
    meldungen = []
    erlaubt = ", ".join(m.capitalize() for m in MENGENARTEN)
    for _, zeile in positionen.iterrows():
        mengenart = zeile["mengenart"]
        if pd.isna(mengenart):
            text = f"Mengenart fehlt (erlaubt: {erlaubt})"
        elif str(mengenart).lower() not in MENGENARTEN:
            text = f"Mengenart «{mengenart}» ist ungültig (erlaubt: {erlaubt})"
        else:
            continue
        meldungen.append(_meldung(FEHLER, "Mengenart", "Positionen", zeile, text))
    return meldungen


def pruefe_preise(positionen):
    """Prueft die Einheitspreise.

    leer -> Hinweis (Position wird «ohne Preis» ausgewiesen)
    kein Zahlwert oder negativ -> Fehler
    0 -> Hinweis (vielleicht vergessen)
    """
    meldungen = []
    for _, zeile in positionen.iterrows():
        preis = zeile["einheitspreis"]
        if pd.isna(preis):
            schwere, text = HINWEIS, "Einheitspreis fehlt, Position wird ohne Preis ausgewiesen"
        elif isinstance(preis, bool) or not isinstance(preis, numbers.Number):
            schwere, text = FEHLER, f"Einheitspreis «{preis}» ist keine Zahl"
        elif preis < 0:
            schwere, text = FEHLER, f"Einheitspreis {preis} ist negativ"
        elif preis == 0:
            schwere, text = HINWEIS, "Einheitspreis ist 0"
        else:
            continue
        meldungen.append(_meldung(schwere, "Preis", "Positionen", zeile, text))
    return meldungen


def pruefe_regeln(zuordnung, positionen):
    """Prueft jede Regel im Blatt Zuordnung (alles Fehler, weil die Regel sonst nicht anwendbar ist):
    Pos-ID fehlt oder ist unbekannt, Vergleich ungueltig, kein einziger Filter ausgefuellt.
    """
    meldungen = []
    bekannte_ids = set(positionen["pos_id"].dropna()) if "pos_id" in positionen.columns else set()

    for _, regel in zuordnung.iterrows():
        if pd.isna(regel["pos_id"]):
            text = "Regel hat keine Pos-ID"
            meldungen.append(_meldung(FEHLER, "Regel Pos-ID", "Zuordnung", regel, text))
        elif bekannte_ids and regel["pos_id"] not in bekannte_ids:
            text = f"Pos-ID {regel['pos_id']} gibt es im Blatt Positionen nicht"
            meldungen.append(_meldung(FEHLER, "Regel Pos-ID", "Zuordnung", regel, text))

        if regel["vergleich"] not in GUELTIGE_VERGLEICHE:
            text = f"Vergleich «{regel['vergleich']}» ist ungültig (erlaubt: gleich, enthält)"
            meldungen.append(_meldung(FEHLER, "Regel Vergleich", "Zuordnung", regel, text))

        if regel[FILTERSPALTEN].isna().all():
            text = "Regel hat keinen Filter ausgefüllt und würde auf alle Bauteile passen"
            meldungen.append(_meldung(FEHLER, "Regel Filter", "Zuordnung", regel, text))
    return meldungen


def pruefe_einstellungen(einstellungen):
    """Meldet Felder und Mengenarten, fuer die im Blatt Einstellungen keine Quelle steht (Fehler)."""
    meldungen = []
    for gruppe, felder in EINSTELLUNGEN_STANDARD.items():
        for feld in felder:
            quelle = einstellungen.get(gruppe, {}).get(feld)
            if quelle is None or any(pd.isna(teil) for teil in quelle):
                text = f"Für «{feld}» ist kein Property-Set / Property-Name angegeben"
                meldungen.append(_meldung(FEHLER, "Einstellungen", "Einstellungen", None, text))
    return meldungen


def pruefe_liste(positionen, zuordnung, einstellungen):
    """Fuehrt alle Pruefungen aus und gibt alle Meldungen als eine Tabelle zurueck.

    Fehlt eine Pflichtspalte, werden die Pruefungen dieses Blatts uebersprungen,
    weil sie sonst abstuerzen wuerden; die fehlende Spalte ist ja schon als Fehler gemeldet.
    """
    meldungen = pruefe_pflichtspalten(positionen, zuordnung)
    if not _fehlende_spalten(positionen, "Positionen"):
        meldungen += pruefe_pos_ids(positionen)
        meldungen += pruefe_mengenarten(positionen)
        meldungen += pruefe_preise(positionen)
    if not _fehlende_spalten(zuordnung, "Zuordnung"):
        meldungen += pruefe_regeln(zuordnung, positionen)
    meldungen += pruefe_einstellungen(einstellungen)
    tabelle = pd.DataFrame(meldungen, columns=MELDUNG_SPALTEN)
    tabelle["excel_zeile"] = tabelle["excel_zeile"].astype("Int64")  # ganze Zahl, darf leer sein
    return tabelle


if __name__ == "__main__":
    # Test im Terminal: python -m validation.list_checks
    from importers.ebkp_reader import lese_ebkp_liste

    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 80)
    positionen, zuordnung, einstellungen = lese_ebkp_liste("daten/eBKP-T_Preisliste_Zuordnung.xlsx")

    print("=== Test 1: Vorlage ===")
    meldungen = pruefe_liste(positionen, zuordnung, einstellungen)
    print("Anzahl Meldungen:", len(meldungen), "(Soll: 0)")
    print("Fehler vorhanden:", hat_fehler(meldungen), "(Soll: False)")

    print("\n=== Test 2: absichtlich veraenderte Kopie ===")
    pos = positionen.astype({"einheitspreis": object})  # Kopie, in der auch Text als Preis erlaubt ist
    pos.loc[1, "pos_id"] = "P01"            # doppelte Pos-ID -> 2 Fehler
    pos.loc[2, "einheitspreis"] = None      # Preis geloescht -> Hinweis
    pos.loc[3, "einheitspreis"] = "45.-"    # Preis als Text -> Fehler
    pos.loc[4, "mengenart"] = "Meter"       # ungueltige Mengenart -> Fehler
    zuo = zuordnung.copy()
    zuo.loc[0, "pos_id"] = "P99"            # unbekannte Pos-ID -> Fehler
    zuo.loc[1, "vergleich"] = "ungefähr"    # ungueltiger Vergleich -> Fehler
    ein = {"felder": dict(einstellungen["felder"]), "mengen": dict(einstellungen["mengen"])}
    del ein["mengen"]["volumen"]             # Einstellung fehlt -> Fehler

    meldungen = pruefe_liste(pos, zuo, ein)
    print(meldungen.to_string())
    print("Fehler vorhanden:", hat_fehler(meldungen), "(Soll: True)")

    print("\n=== Test 3: Pflichtspalte fehlt ===")
    meldungen = pruefe_liste(positionen.drop(columns="einheitspreis"), zuordnung, einstellungen)
    print(meldungen.to_string())
