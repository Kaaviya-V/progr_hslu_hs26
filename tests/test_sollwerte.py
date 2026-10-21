"""Vergleich mit den Sollwerten im Blatt «Kontrolle» der eBKP-T-Liste.

Ausfuehren im Terminal: python -m pytest tests -v
Die IFC-Dateien liegen nur lokal in daten/; fehlen sie, werden die Tests uebersprungen.

Toleranz: Das Blatt rechnet mit auf 3 Stellen gerundeten Mengen, das Programm mit
den exakten IFC-Werten (Total 896'542.12 statt 896'542.43). Deshalb nicht exakt vergleichen.
"""

from pathlib import Path

import pandas as pd
import pytest

from calculation.costs import berechne_kosten, berechne_total
from calculation.mapping import ordne_zu
from importers.ebkp_reader import lese_ebkp_liste
from importers.ifc_reader import lese_alle_ifc
from validation.list_checks import pruefe_liste
from validation.model_checks import hat_fehler, pruefe_modell

DATEN = Path(__file__).parent.parent / "daten"
LISTE = DATEN / "eBKP-T_Preisliste_Zuordnung.xlsx"

TOLERANZ_MENGE = 0.01   # in der Einheit der Position
TOLERANZ_CHF = 1.0
SOLL_TOTAL = 896_542.43
SOLL_BAUTEILE = 852

if not LISTE.exists() or not list(DATEN.glob("*.ifc")):
    pytest.skip("IFC-Dateien oder eBKP-T-Liste fehlen in daten/", allow_module_level=True)


@pytest.fixture(scope="module")
def ergebnis():
    """Ganzer Ablauf einmal fuer alle Tests (das Einlesen der IFC dauert ein paar Sekunden)."""
    positionen, zuordnung, einstellungen = lese_ebkp_liste(LISTE)
    bauteile = lese_alle_ifc(DATEN, einstellungen)
    zugeordnet, zuordnungsmeldungen = ordne_zu(bauteile, zuordnung, positionen)
    kosten, _, _ = berechne_kosten(zugeordnet, positionen)
    return {
        "positionen": positionen,
        "zuordnung": zuordnung,
        "einstellungen": einstellungen,
        "bauteile": bauteile,
        "zuordnungsmeldungen": zuordnungsmeldungen,
        "kosten": kosten.set_index("pos_id"),
    }


@pytest.fixture(scope="module")
def soll():
    """Blatt «Kontrolle»: nur die Zeilen mit Pos-ID (ohne Total und Zusammenfassung)."""
    kontrolle = pd.read_excel(LISTE, sheet_name="Kontrolle", header=3)
    kontrolle = kontrolle.dropna(subset=["Pos-ID"])
    return kontrolle.set_index("Pos-ID")


def test_anzahl_bauteile(ergebnis):
    assert len(ergebnis["bauteile"]) == SOLL_BAUTEILE


def test_modell_ohne_fehler(ergebnis):
    assert not hat_fehler(pruefe_modell(ergebnis["bauteile"]))


def test_liste_ohne_meldungen(ergebnis):
    meldungen = pruefe_liste(ergebnis["positionen"], ergebnis["zuordnung"], ergebnis["einstellungen"])
    assert len(meldungen) == 0


def test_zuordnung_ohne_meldungen(ergebnis):
    """Alle Bauteile genau einer Position, 0 Konflikte, keine Position ohne Bauteil."""
    assert len(ergebnis["zuordnungsmeldungen"]) == 0


def test_gleiche_pos_ids(ergebnis, soll):
    assert set(ergebnis["kosten"].index) == set(soll.index)


@pytest.mark.parametrize("spalte_ist, spalte_soll, toleranz", [
    ("anzahl_bauteile", "Anzahl Bauteile", 0),
    ("menge", "Menge", TOLERANZ_MENGE),
    ("kosten", "Kosten (CHF)", TOLERANZ_CHF),
])
def test_werte_je_position(ergebnis, soll, spalte_ist, spalte_soll, toleranz):
    """Vergleicht eine Spalte fuer alle Pos-IDs und listet alle Abweichungen auf einmal auf."""
    ist = ergebnis["kosten"][spalte_ist]
    erwartet = soll[spalte_soll].reindex(ist.index)
    abweichung = (ist - erwartet).abs()
    falsch = abweichung[abweichung > toleranz]
    assert falsch.empty, f"{spalte_ist} weicht ab bei: " + ", ".join(
        f"{pos_id} (ist {ist[pos_id]}, soll {erwartet[pos_id]})" for pos_id in falsch.index
    )


def test_total(ergebnis):
    assert berechne_total(ergebnis["kosten"]) == pytest.approx(SOLL_TOTAL, abs=TOLERANZ_CHF)


def test_beispiele_aus_claude_md(ergebnis):
    """Die Beispiele aus CLAUDE.md, gerundet auf 1 Stelle."""
    kosten = ergebnis["kosten"]
    assert round(kosten.loc["P01", "menge"], 1) == 1186.9
    assert round(kosten.loc["P08", "menge"], 1) == 704.8
    assert round(kosten.loc["P22", "menge"], 1) == 300.7
    assert round(kosten.loc["P30", "menge"], 1) == 76.6
    assert kosten.loc["P30", "anzahl_bauteile"] == 61


def test_nagelwand_mit_hinweis(ergebnis):
    """Nagelwand hat keine Fläche: Menge 0, aber sichtbar als Hinweis, nicht still."""
    nagelwand = ergebnis["kosten"].loc["P37"]
    assert nagelwand["menge"] == 0
    assert "Menge 0" in nagelwand["hinweis"]
