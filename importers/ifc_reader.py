"""IFC lesen: eine Zeile pro Bauteil mit GUID, Klasse, neutralen Feldern, Mengen und Hierarchie."""

from pathlib import Path

import ifcopenshell
import ifcopenshell.util.element
import pandas as pd

# Woher die Werte kommen: neutrales Feld -> (Property-Set, Property-Name).
# Spaeter ersetzt durch das Blatt «Einstellungen» der eBKP-T-Liste.
EINSTELLUNGEN_STANDARD = {
    "felder": {
        "bereich": ("GoBau_Struktur", "Stufe_4"),
        "bauteilgruppe": ("GoBau_Struktur", "Stufe_5"),
        "typ_schicht": ("GoBau_Struktur", "Stufe_6"),
        "element": ("GoBau_Struktur", "Stufe_7"),
    },
    "mengen": {
        "anzahl": ("GoBau_Menge", "Anzahl (Stk.)"),
        "laenge": ("GoBau_Menge", "Länge (m)"),
        "flaeche": ("GoBau_Menge", "Fläche (m2)"),
        "volumen": ("GoBau_Menge", "Volumen (m3)"),
    },
}

# Diese Klassen sind keine eigenen Bauteile und werden nicht gezaehlt
IGNORIERTE_KLASSEN = ["IfcElementAssembly", "IfcAnnotation"]

HIERARCHIE_SPALTEN = ["ifc_bereich", "ifc_bauteilgruppe", "ifc_baugruppe"]

# Begrenzungsbox, wie Civil 3D sie exportiert (fuer die Duplikat-Pruefung)
BEGRENZUNGSBOX = ("Properties", "Bounds")


def _bereinige(wert):
    """Entfernt Leerzeichen am Rand; leere Texte werden zu None."""
    if isinstance(wert, str):
        wert = wert.strip()
        if wert == "":
            return None
    return wert


def _lese_hierarchie(bauteil):
    """Sucht die uebergeordneten IfcRoadPart und die IfcElementAssembly eines Bauteils."""
    roadparts = []
    baugruppe = None
    eltern = ifcopenshell.util.element.get_aggregate(bauteil) or ifcopenshell.util.element.get_container(bauteil)
    while eltern is not None:
        if eltern.is_a("IfcRoadPart"):
            roadparts.append(_bereinige(eltern.Name))
        elif eltern.is_a("IfcElementAssembly") and baugruppe is None:
            baugruppe = _bereinige(eltern.Name)
        eltern = ifcopenshell.util.element.get_aggregate(eltern) or ifcopenshell.util.element.get_container(eltern)

    return {
        # oberster IfcRoadPart = Bereich, direkt uebergeordneter = Bauteilgruppe
        "ifc_bereich": roadparts[-1] if roadparts else None,
        "ifc_bauteilgruppe": roadparts[0] if roadparts else None,
        "ifc_baugruppe": baugruppe,
    }


def lese_ifc(pfad, einstellungen=EINSTELLUNGEN_STANDARD):
    """Liest eine IFC-Datei und gibt eine Tabelle mit einer Zeile pro Bauteil zurueck."""
    pfad = Path(pfad)
    modell = ifcopenshell.open(str(pfad))
    return _lese_bauteile(modell, pfad.name, einstellungen)


def lese_hochgeladene_ifc(dateien, einstellungen=EINSTELLUNGEN_STANDARD):
    """Liest IFC-Dateien, die nur im Arbeitsspeicher liegen (z.B. Upload in Streamlit).

    Jede Datei braucht .name (Dateiname) und .getvalue() (Inhalt als Bytes).
    """
    tabellen = []
    for datei in dateien:
        modell = ifcopenshell.file.from_string(datei.getvalue().decode("utf-8"))
        tabellen.append(_lese_bauteile(modell, datei.name, einstellungen))
    return pd.concat(tabellen, ignore_index=True)


def _lese_bauteile(modell, dateiname, einstellungen):
    """Eine Zeile pro Bauteil eines geoeffneten IFC-Modells."""
    fachmodell = Path(dateiname).stem.split("_")[-1]  # "25.011_N_WKLN-EW" -> "WKLN-EW"

    zeilen = []
    for bauteil in modell.by_type("IfcElement"):
        if bauteil.is_a() in IGNORIERTE_KLASSEN:
            continue

        psets = ifcopenshell.util.element.get_psets(bauteil)

        zeile = {
            "datei": dateiname,
            "fachmodell": fachmodell,
            "guid": bauteil.GlobalId,
            "klasse": bauteil.is_a(),
            "name": _bereinige(bauteil.Name),
        }

        # Neutrale Felder aus dem eingestellten Property Set
        for feld, (pset_name, property_name) in einstellungen["felder"].items():
            zeile[feld] = _bereinige(psets.get(pset_name, {}).get(property_name))

        # Mengen; die Quelle merken wir uns, sobald mindestens eine Menge gefunden wurde
        mengenquelle = None
        for menge, (pset_name, property_name) in einstellungen["mengen"].items():
            wert = psets.get(pset_name, {}).get(property_name)
            zeile[menge] = wert
            if wert is not None:
                mengenquelle = pset_name
        zeile["mengenquelle"] = mengenquelle

        zeile.update(_lese_hierarchie(bauteil))
        zeile["begrenzungsbox"] = psets.get(BEGRENZUNGSBOX[0], {}).get(BEGRENZUNGSBOX[1])
        zeilen.append(zeile)

    spalten = ["datei", "fachmodell", "guid", "klasse", "name"]
    spalten += list(einstellungen["felder"]) + list(einstellungen["mengen"])
    spalten += ["mengenquelle"] + HIERARCHIE_SPALTEN + ["begrenzungsbox"]
    return pd.DataFrame(zeilen, columns=spalten)


def lese_mehrere_ifc(pfade, einstellungen=EINSTELLUNGEN_STANDARD):
    """Liest eine oder mehrere IFC-Dateien und haengt die Tabellen untereinander."""
    if isinstance(pfade, (str, Path)):
        pfade = [pfade]
    tabellen = [lese_ifc(pfad, einstellungen) for pfad in pfade]
    return pd.concat(tabellen, ignore_index=True)


def lese_alle_ifc(ordner, einstellungen=EINSTELLUNGEN_STANDARD):
    """Liest alle IFC-Dateien eines Ordners."""
    return lese_mehrere_ifc(sorted(Path(ordner).glob("*.ifc")), einstellungen)


if __name__ == "__main__":
    # Test im Terminal: python -m importers.ifc_reader
    bauteile = lese_alle_ifc("daten")

    print("Anzahl Bauteile pro Fachmodell:")
    print(bauteile.groupby("fachmodell").size().to_string())
    print("Total:", len(bauteile), "(Soll: 852)")

    print("\nBauteile ohne Mengenquelle:", bauteile["mengenquelle"].isna().sum())
    print("\nBeispielzeile:")
    print(bauteile.iloc[0].to_string())
