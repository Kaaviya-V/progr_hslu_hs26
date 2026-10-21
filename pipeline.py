"""Durchlauf ohne Webseite: Schritte 1-7 nacheinander.

Haelt an, sobald eine Pruefung einen Fehler meldet (Hinweise erlauben das Weiterfahren).
main.py ruft spaeter nur diese Funktionen auf, damit keine Fachlogik in der Oberflaeche steht.

Reihenfolge: Die eBKP-T-Liste wird zuerst GELESEN, weil ihr Blatt «Einstellungen» sagt,
aus welchen Property-Sets die IFC-Werte kommen. GEPRUEFT wird sie erst nach dem Modell.

Ausfuehren im Terminal: python pipeline.py [ifc-ordner] [ebkp-liste] [ziel.xlsx]
"""

import sys
from pathlib import Path

from calculation.costs import berechne_kosten, berechne_total
from calculation.mapping import ordne_zu
from export.excel_writer import schreibe_kostenschaetzung
from importers.ebkp_reader import lese_ebkp_liste
from importers.ifc_reader import lese_mehrere_ifc
from validation.list_checks import pruefe_liste
from validation.model_checks import FEHLER, hat_fehler, pruefe_modell


def fuehre_aus(ifc_dateien, liste, ziel=None):
    """Fuehrt alle Schritte aus und gibt ein Dictionary mit allen Zwischenergebnissen zurueck.

    ifc_dateien: Liste von Pfaden zu IFC-Dateien
    liste:       Pfad zur eBKP-T-Liste
    ziel:        Pfad fuer die Excel-Kostenschaetzung; None -> Excel als Bytes in ergebnis["excel"]

    ergebnis["gestoppt_bei"] ist None, wenn alles durchlief, sonst der Name des Schritts mit Fehlern.
    Die Meldungen aller ausgefuehrten Schritte stehen in ergebnis["meldungen"].
    """
    ergebnis = {"gestoppt_bei": None, "meldungen": {}}
    meldungen = ergebnis["meldungen"]

    # Einlesen (Schritt 4 lesen, dann Schritt 1)
    positionen, zuordnung, einstellungen = lese_ebkp_liste(liste)
    bauteile = lese_mehrere_ifc(ifc_dateien, einstellungen)
    ergebnis.update(positionen=positionen, zuordnung=zuordnung, einstellungen=einstellungen, bauteile=bauteile)

    # Schritt 2 + 3: Modell pruefen und entscheiden
    meldungen["Modellprüfung"] = pruefe_modell(bauteile)
    if hat_fehler(meldungen["Modellprüfung"]):
        ergebnis["gestoppt_bei"] = "Modellprüfung"
        return ergebnis

    # Schritt 4: Liste pruefen
    meldungen["Listenprüfung"] = pruefe_liste(positionen, zuordnung, einstellungen)
    if hat_fehler(meldungen["Listenprüfung"]):
        ergebnis["gestoppt_bei"] = "Listenprüfung"
        return ergebnis

    # Schritt 5: Zuordnen (Konflikte sind Fehler)
    zugeordnet, meldungen["Zuordnung"] = ordne_zu(bauteile, zuordnung, positionen)
    ergebnis["bauteile"] = zugeordnet
    if hat_fehler(meldungen["Zuordnung"]):
        ergebnis["gestoppt_bei"] = "Zuordnung"
        return ergebnis

    # Schritt 6: Berechnen
    kosten, bauteilkosten, meldungen["Berechnung"] = berechne_kosten(zugeordnet, positionen)
    ergebnis.update(kosten=kosten, bauteile=bauteilkosten, total=berechne_total(kosten))

    # Schritt 7: Exportieren
    ergebnis["excel"] = schreibe_kostenschaetzung(
        kosten, bauteilkosten, meldungen, ifc_dateien, Path(liste).name, ziel
    )
    return ergebnis


def zusammenfassung_text(ergebnis):
    """Kurzer Text fuer das Terminal: Meldungen je Schritt und Total bzw. wo gestoppt wurde."""
    zeilen = []
    for schritt, tabelle in ergebnis["meldungen"].items():
        fehler = (tabelle["schwere"] == FEHLER).sum()
        zeilen.append(f"{schritt:15} {fehler:4} Fehler {len(tabelle) - fehler:4} Hinweise")
    if ergebnis["gestoppt_bei"]:
        zeilen.append(f"GESTOPPT bei «{ergebnis['gestoppt_bei']}». Fehler:")
        tabelle = ergebnis["meldungen"][ergebnis["gestoppt_bei"]]
        for text in tabelle.loc[tabelle["schwere"] == FEHLER, "meldung"]:
            zeilen.append(f"  - {text}")
    else:
        total = f"{ergebnis['total']:,.2f}".replace(",", "'")
        zeilen.append(f"Total exkl. MwSt.: CHF {total}")
    return "\n".join(zeilen)


if __name__ == "__main__":
    ordner = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("daten")
    liste = Path(sys.argv[2]) if len(sys.argv) > 2 else ordner / "eBKP-T_Preisliste_Zuordnung.xlsx"
    ziel = Path(sys.argv[3]) if len(sys.argv) > 3 else ordner / "Kostenschaetzung.xlsx"

    ifc_dateien = sorted(ordner.glob("*.ifc"))
    print(f"{len(ifc_dateien)} IFC-Dateien, Liste {liste.name}")
    ergebnis = fuehre_aus(ifc_dateien, liste, ziel)
    print(zusammenfassung_text(ergebnis))
    if not ergebnis["gestoppt_bei"]:
        print("Gespeichert:", ziel)
