"""IFC-Gesamtmodell: Fachmodelle zusammenfuehren und mit den KOSTRA-Ergebnissen anreichern.

1. Alle Fachmodelle in eine neue Datei kopieren, unter EINEM IfcProject.
   GUIDs bleiben unveraendert; die Originaldateien werden nie veraendert.
2. Jedes Bauteil bekommt das Property-Set Pset_KOSTRA (Pos-ID, Menge, Kosten, Status, Herkunft ...).
3. Ist in der Liste ein eBKP-T-Code eingetragen, wird er als IfcClassificationReference zugewiesen.

Herkunft sichtbar: Pset_KOSTRA.Fachmodell / Quelldatei, und die obersten Raumelemente
(z.B. IfcRoad «Gimenenstrasse») bekommen das Fachmodell im Namen: «Gimenenstrasse (TRAS)».
"""

from pathlib import Path

import ifcopenshell
import ifcopenshell.api.classification
import ifcopenshell.api.pset
import ifcopenshell.util.element
import pandas as pd

PSET_NAME = "Pset_KOSTRA"
KLASSIFIKATION = "eBKP-T"

STATUS_ZUGEORDNET = "zugeordnet"
STATUS_OHNE_PREIS = "ohne Preis"
STATUS_KONFLIKT = "Konflikt"


# ------------------------------------------------------------------ 1 Zusammenfuehren

def _ersetze_ueberall(datei, alt, neu):
    """Haengt alle Verweise auf alt (z.B. ein Projekt) auf neu um."""
    for verweis in datei.get_inverse(alt):
        ifcopenshell.util.element.replace_attribute(verweis, alt, neu)


def _passender_kontext(kontext, haupt_kontexte):
    """Sucht im Hauptprojekt den Darstellungskontext mit gleicher Art (Model/Plan, Body/Axis ...)."""
    for kandidat in haupt_kontexte:
        if (kandidat.is_a() == kontext.is_a()
                and kandidat.ContextType == kontext.ContextType
                and kandidat.ContextIdentifier == kontext.ContextIdentifier
                and getattr(kandidat, "TargetView", None) == getattr(kontext, "TargetView", None)):
            return kandidat
    return None


def _haenge_projekt_um(ziel, haupt, projekt):
    """Verschiebt alles vom zusaetzlichen Projekt ins Hauptprojekt und loescht es danach."""
    # Darstellungskontexte: gleiche Kontexte zusammenlegen, damit es pro Art nur einen gibt
    haupt_kontexte = ziel.by_type("IfcGeometricRepresentationContext")
    haupt_kontexte = [k for k in haupt_kontexte if _gehoert_zu(k, haupt)]
    for kontext in [k for k in ziel.by_type("IfcGeometricRepresentationContext") if _gehoert_zu(k, projekt)]:
        ersatz = _passender_kontext(kontext, haupt_kontexte)
        if ersatz is not None:
            _ersetze_ueberall(ziel, kontext, ersatz)
            ziel.remove(kontext)

    einheiten = projekt.UnitsInContext
    _ersetze_ueberall(ziel, projekt, haupt)   # Aggregation, Klassifikation, Deklarationen
    ziel.remove(projekt)
    if einheiten is not None and ziel.get_total_inverses(einheiten) == 0:
        ziel.remove(einheiten)


def _gehoert_zu(kontext, projekt):
    """True, wenn ein (Unter-)Kontext zu diesem Projekt gehoert."""
    while kontext.is_a("IfcGeometricRepresentationSubContext"):
        kontext = kontext.ParentContext
    return kontext in (projekt.RepresentationContexts or ())


def _markiere_herkunft(ziel, projekt_vorher, fachmodell):
    """Haengt den Fachmodell-Namen an die obersten Raumelemente dieses Modells an."""
    for beziehung in projekt_vorher.IsDecomposedBy:
        for element in beziehung.RelatedObjects:
            element.Name = f"{element.Name} ({fachmodell})"


def fuehre_modelle_zusammen(modelle):
    """Kopiert mehrere IFC-Modelle in eine neue Datei unter einem gemeinsamen IfcProject.

    modelle: Liste von (dateiname, ifcopenshell.file)
    Das erste Projekt bleibt das Hauptprojekt, die anderen werden darin eingehaengt.
    """
    ziel = ifcopenshell.file(schema=modelle[0][1].schema)
    haupt = None

    for dateiname, modell in modelle:
        fachmodell = Path(dateiname).stem.split("_")[-1]
        for element in modell:
            ziel.add(element)          # kopiert das Element mit allem, worauf es verweist
        projekt = ziel.by_guid(modell.by_type("IfcProject")[0].GlobalId)
        _markiere_herkunft(ziel, projekt, fachmodell)

        if haupt is None:
            haupt = projekt
        else:
            _haenge_projekt_um(ziel, haupt, projekt)

    _entferne_doppelte_programme(ziel)
    return ziel


def _entferne_doppelte_programme(ziel):
    """Jede Datei bringt ihr IfcApplication («Civil 3D 2026») mit; IFC erlaubt es nur einmal."""
    erstes = {}
    for programm in ziel.by_type("IfcApplication"):
        if programm.ApplicationIdentifier in erstes:
            _ersetze_ueberall(ziel, programm, erstes[programm.ApplicationIdentifier])
            ziel.remove(programm)
        else:
            erstes[programm.ApplicationIdentifier] = programm


# ------------------------------------------------------------------ 2 + 3 Anreichern

def _status(bauteil):
    if pd.notna(bauteil["pos_id"]):
        return STATUS_ZUGEORDNET
    if isinstance(bauteil.get("treffer_pos_ids"), str) and "," in bauteil["treffer_pos_ids"]:
        return STATUS_KONFLIKT
    return STATUS_OHNE_PREIS


def _wert(wert):
    """Leere Werte (NaN) weglassen und numpy-Zahlen in normale Python-Zahlen umwandeln."""
    if pd.isna(wert):
        return None
    return wert.item() if hasattr(wert, "item") else wert


def kostra_eigenschaften(bauteil):
    """Die Eigenschaften fuer Pset_KOSTRA eines Bauteils (leere werden weggelassen)."""
    eigenschaften = {
        "Status": _status(bauteil),
        "PosID": bauteil.get("pos_id"),
        "Bezeichnung": bauteil.get("bezeichnung"),
        "Mengenart": bauteil.get("mengenart"),
        "Menge": bauteil.get("menge"),
        "Einheit": bauteil.get("einheit"),
        "Einheitspreis": bauteil.get("einheitspreis"),
        "Kosten": bauteil.get("kosten"),
        "Mengenquelle": bauteil.get("mengenquelle"),
        "Regel": bauteil.get("treffer_regeln"),
        "Ersatzfelder": bauteil.get("ersatzfelder"),
        "Fachmodell": bauteil.get("fachmodell"),
        "Quelldatei": bauteil.get("datei"),
    }
    if eigenschaften["Status"] == STATUS_KONFLIKT:
        eigenschaften["PosID"] = bauteil["treffer_pos_ids"]
    eigenschaften = {name: _wert(wert) for name, wert in eigenschaften.items()}
    return {name: wert for name, wert in eigenschaften.items() if wert is not None}


def ergaenze_kostra(ziel, bauteile, positionen):
    """Haengt jedem Bauteil Pset_KOSTRA an und, falls vorhanden, den eBKP-T-Code.

    bauteile: Ergebnis von berechne_kosten (mit pos_id, menge, kosten ...)
    Gibt die Anzahl angereicherter Bauteile zurueck.
    """
    infos = positionen[["pos_id", "bezeichnung", "mengenart", "ebkp_code"]]
    bauteile = bauteile.merge(infos, on="pos_id", how="left")

    klassifikation = None
    referenzen = {}          # eBKP-T-Code -> IfcClassificationReference (jede nur einmal anlegen)
    angereichert = 0

    for _, bauteil in bauteile.iterrows():
        element = ziel.by_guid(bauteil["guid"])
        pset = ifcopenshell.api.pset.add_pset(ziel, product=element, name=PSET_NAME)
        ifcopenshell.api.pset.edit_pset(ziel, pset=pset, properties=kostra_eigenschaften(bauteil))
        angereichert += 1

        code = bauteil["ebkp_code"]
        if pd.notna(code) and str(code).strip():
            code = str(code).strip()
            if klassifikation is None:
                klassifikation = ifcopenshell.api.classification.add_classification(ziel, classification=KLASSIFIKATION)
            if code not in referenzen:
                referenzen[code] = ifcopenshell.api.classification.add_reference(
                    ziel, products=[element], identification=code,
                    name=bauteil["bezeichnung"], classification=klassifikation)
            else:
                ifcopenshell.api.classification.add_reference(
                    ziel, products=[element], reference=referenzen[code], classification=klassifikation)
    return angereichert


# ------------------------------------------------------------------ Alles zusammen

def oeffne_ifc(pfade):
    """Oeffnet IFC-Dateien von der Festplatte: Liste von (dateiname, modell)."""
    return [(Path(pfad).name, ifcopenshell.open(str(pfad))) for pfad in pfade]


def oeffne_hochgeladene_ifc(dateien):
    """Oeffnet hochgeladene IFC-Dateien (Streamlit): Liste von (dateiname, modell)."""
    return [(d.name, ifcopenshell.file.from_string(d.getvalue().decode("utf-8"))) for d in dateien]


def schreibe_gesamtmodell(modelle, bauteile, positionen, ziel=None):
    """Erstellt das Gesamtmodell. ziel = Pfad zum Speichern; None -> Inhalt als Bytes zurueck."""
    gesamt = fuehre_modelle_zusammen(modelle)
    ergaenze_kostra(gesamt, bauteile, positionen)
    if ziel is None:
        return gesamt.to_string().encode("utf-8")
    gesamt.write(str(ziel))
    return None


if __name__ == "__main__":
    # Test im Terminal: python -m export.ifc_writer [ALLE]
    # Ohne Argument nur SIMA + AUSS (klein, schnell), mit ALLE alle 9 Modelle.
    import sys

    from calculation.costs import berechne_kosten
    from calculation.mapping import ordne_zu
    from importers.ebkp_reader import lese_ebkp_liste
    from importers.ifc_reader import lese_ifc, lese_mehrere_ifc

    alle = len(sys.argv) > 1 and sys.argv[1].upper() == "ALLE"
    pfade = sorted(Path("daten").glob("*.ifc"))
    if not alle:
        pfade = [p for p in pfade if p.stem.endswith(("SIMA", "AUSS"))]
    # Eigener Unterordner: sonst wuerde das Gesamtmodell beim naechsten Einlesen von daten/*.ifc
    # als zusaetzliches Fachmodell mitgelesen (alle Bauteile doppelt)
    ziel = Path("daten/ausgabe/KOSTRA_Gesamtmodell.ifc")
    ziel.parent.mkdir(exist_ok=True)

    positionen, zuordnung, einstellungen = lese_ebkp_liste("daten/eBKP-T_Preisliste_Zuordnung.xlsx")
    bauteile, _ = ordne_zu(lese_mehrere_ifc(pfade, einstellungen), zuordnung, positionen)
    _, bauteilkosten, _ = berechne_kosten(bauteile, positionen)

    schreibe_gesamtmodell(oeffne_ifc(pfade), bauteilkosten, positionen, ziel)
    print("Gespeichert:", ziel, f"({ziel.stat().st_size / 1e6:.1f} MB)")

    # ---- Kontrolle: Gesamtmodell wieder einlesen
    gesamt = ifcopenshell.open(str(ziel))
    print("IfcProject:", len(gesamt.by_type("IfcProject")), "(Soll: 1)")
    print("Hauptkontexte:", [k.ContextType for k in gesamt.by_type("IfcGeometricRepresentationContext")
                             if not k.is_a("IfcGeometricRepresentationSubContext")], "(Soll: ['Model'])")
    print("Oberste Raumelemente:", [e.Name for r in gesamt.by_type("IfcProject")[0].IsDecomposedBy
                                     for e in r.RelatedObjects])

    # Die zusaetzlichen IfcProject sind absichtlich weg (ins Hauptprojekt eingehaengt)
    vorher = {e.GlobalId for p in pfade for e in ifcopenshell.open(str(p)).by_type("IfcRoot")
              if not e.is_a("IfcProject")}
    nachher = {e.GlobalId for e in gesamt.by_type("IfcRoot")}
    print("GUIDs aus den Fachmodellen alle vorhanden (ohne IfcProject):", vorher <= nachher)

    neu_gelesen = lese_ifc(ziel, einstellungen)
    print("Bauteile im Gesamtmodell:", len(neu_gelesen), "(Soll:", len(bauteilkosten), ")")
    mit_pset = sum(1 for g in bauteilkosten["guid"]
                   if PSET_NAME in ifcopenshell.util.element.get_psets(gesamt.by_guid(g)))
    print(f"Bauteile mit {PSET_NAME}:", mit_pset)

    beispiel = gesamt.by_guid(bauteilkosten["guid"].iloc[0])
    print("Beispiel", beispiel.is_a(), beispiel.Name)
    for name, wert in ifcopenshell.util.element.get_psets(beispiel)[PSET_NAME].items():
        print(f"   {name:15} {wert}")

    kosten_ifc = sum(ifcopenshell.util.element.get_psets(gesamt.by_guid(g))[PSET_NAME].get("Kosten", 0)
                     for g in bauteilkosten["guid"])
    print(f"Summe Kosten im IFC: {kosten_ifc:,.2f}   Summe Programm: {bauteilkosten['kosten'].sum():,.2f}")
