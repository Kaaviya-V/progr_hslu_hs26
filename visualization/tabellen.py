"""Tabellen fuer die Anzeige aufbereiten (Formatierung, Spaltennamen, Status-Symbole).

Hier steht nur Darstellung, keine Fachlogik: Die Werte kommen fertig berechnet aus
calculation/ und validation/; diese Funktionen machen sie lesbar fuer die Oberflaeche.
"""

import pandas as pd
import streamlit as st

from validation.model_checks import FEHLER

OK, WARNUNG, FEHLT, OFFEN = "✓", "⚠", "✗", "○"


# ------------------------------------------------------------------ Zahlen als Text

def zahl(wert, stellen=0):
    """Zahl mit Apostroph als Tausendertrenner: 1234567.8 -> 1'234'568 (stellen=0)."""
    if pd.isna(wert):
        return ""
    return f"{wert:,.{stellen}f}".replace(",", "'")


def menge_mit_einheit(menge, einheit, mengenart):
    """Stueck ohne Nachkommastellen, sonst 1 Stelle, mit Einheit: «1'186.9 m²», «22 Stk»."""
    if pd.isna(menge):
        return ""
    stellen = 0 if str(mengenart).lower() == "stück" else 1
    return f"{zahl(menge, stellen)} {einheit if pd.notna(einheit) else ''}".strip()


# ------------------------------------------------------------------ Status

def status(meldungen):
    """Status-Symbol einer Pruefung: ✓ keine Meldung, ⚠ nur Hinweise, ✗ mindestens ein Fehler."""
    if meldungen is None:
        return OFFEN
    if (meldungen["schwere"] == FEHLER).any():
        return FEHLT
    if len(meldungen):
        return WARNUNG
    return OK


def anzahl_text(meldungen):
    """Kurzer Text wie «2 Fehler · 5 Hinweise» oder «keine Meldungen»."""
    if meldungen is None:
        return "noch nicht ausgeführt"
    fehler = int((meldungen["schwere"] == FEHLER).sum())
    hinweise = len(meldungen) - fehler
    hinweis_wort = "Hinweis" if hinweise == 1 else "Hinweise"
    teile = ([f"{fehler} Fehler"] if fehler else []) + ([f"{hinweise} {hinweis_wort}"] if hinweise else [])
    return " · ".join(teile) or "keine Meldungen"


# ------------------------------------------------------------------ Tabellen

def meldungen_tabelle(meldungen):
    """Alle Meldungen: Prüfung (mit ✗/⚠), Fachmodell, Pos-ID, GUID, Meldung. Fehler zuerst."""
    tabelle = pd.DataFrame({
        "Prüfung": [f"{FEHLT if s == FEHLER else WARNUNG} {p}"
                    for s, p in zip(meldungen["schwere"], meldungen["pruefung"])],
        "Fachmodell": meldungen.get("fachmodell"),
        "Pos-ID": meldungen.get("pos_id"),
        "GUID": meldungen.get("guid"),
        "Meldung": meldungen["meldung"],
    })
    return tabelle.fillna("")


def kosten_tabelle(kosten, gruppe=None, suche=""):
    """Kosten je Position fuer die Anzeige: gefiltert, nach Kosten sortiert, formatiert.

    gruppe: nur diese Gruppe (None = alle); suche: Text in Pos-ID oder Bezeichnung.
    """
    tabelle = kosten
    if gruppe:
        tabelle = tabelle[tabelle["gruppe"] == gruppe]
    if suche:
        treffer = (tabelle["pos_id"].str.contains(suche, case=False, regex=False)
                   | tabelle["bezeichnung"].str.contains(suche, case=False, regex=False))
        tabelle = tabelle[treffer]
    tabelle = tabelle.sort_values("kosten", ascending=False, na_position="last")

    return pd.DataFrame({
        "Pos-ID": tabelle["pos_id"],
        "Gruppe": tabelle["gruppe"],
        "Bezeichnung": tabelle["bezeichnung"],
        "Bauteile": tabelle["anzahl_bauteile"],
        "Menge": [menge_mit_einheit(m, e, a) for m, e, a
                  in zip(tabelle["menge"], tabelle["einheit"], tabelle["mengenart"])],
        "EP CHF": tabelle["einheitspreis"].map(lambda w: zahl(w, 2)),
        "Kosten CHF": tabelle["kosten"].map(lambda w: zahl(w, 2)),
        "Anteil": tabelle["anteil"],
        "Hinweis": tabelle["hinweis"].fillna(""),
    })


# Spaltenformat fuer st.dataframe. Menge, EP und Kosten sind schon Text (wegen des Apostrophs);
# ein Klick auf den Spaltenkopf wuerde sie alphabetisch sortieren, darum kommt die Tabelle
# bereits nach Kosten sortiert aus kosten_tabelle.
KOSTEN_SPALTEN = {
    "Pos-ID": st.column_config.TextColumn("Pos-ID", width="small"),
    "Gruppe": st.column_config.TextColumn("Gruppe", width="medium"),
    "Bezeichnung": st.column_config.TextColumn("Bezeichnung", width="large"),
    "Bauteile": st.column_config.NumberColumn("Bauteile", format="%d", width="small"),
    "Menge": st.column_config.TextColumn("Menge", width="small"),
    "EP CHF": st.column_config.TextColumn("EP CHF", width="small"),
    "Kosten CHF": st.column_config.TextColumn("Kosten CHF", width="small"),
    "Anteil": st.column_config.ProgressColumn("Anteil", format="percent", min_value=0, max_value=1, width="small"),
    "Hinweis": st.column_config.TextColumn("Hinweis", width="medium"),
}


def bauteile_tabelle(bauteile):
    """Bauteilliste: Fachmodell, GUID, IFC-Klasse, Typ/Schicht, Pos-ID, Menge, Mengenquelle.

    Die Menge ist die massgebende Menge (nach Mengenart der Position), sobald berechnet.
    """
    if "menge" in bauteile.columns:
        menge = [menge_mit_einheit(m, e, "stück" if s == "anzahl" else "")
                 for m, e, s in zip(bauteile["menge"], bauteile["einheit"], bauteile["mengenspalte"])]
    else:
        menge = ""
    return pd.DataFrame({
        "Fachmodell": bauteile["fachmodell"],
        "GUID": bauteile["guid"],
        "IFC-Klasse": bauteile["klasse"],
        "Typ / Schicht": bauteile["typ_schicht"],
        "Pos-ID": bauteile["pos_id"] if "pos_id" in bauteile.columns else "",
        "Menge": menge,
        "Mengenquelle": bauteile["mengenquelle"],
    }).fillna("")
