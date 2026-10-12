"""IFC lesen: Bauteile mit GlobalId, GoBau_Struktur und GoBau_Menge als Tabelle."""

from pathlib import Path

import ifcopenshell
import ifcopenshell.util.element
import pandas as pd

# Name im IFC (GoBau_Menge) -> Spaltenname in der Tabelle
MENGEN = {
    "Anzahl (Stk.)": "anzahl",
    "Länge (m)": "laenge",
    "Fläche (m2)": "flaeche",
    "Volumen (m3)": "volumen",
}

STUFEN = ["Stufe_1", "Stufe_2", "Stufe_3", "Stufe_4", "Stufe_5", "Stufe_6", "Stufe_7"]


def lese_ifc(pfad):
    """Liest eine IFC-Datei und gibt eine Tabelle mit einer Zeile pro Bauteil zurueck."""
    pfad = Path(pfad)
    modell = ifcopenshell.open(str(pfad))
    fachmodell = pfad.stem.split("_")[-1]

    zeilen = []
    for bauteil in modell.by_type("IfcProduct"):
        if bauteil.is_a("IfcAnnotation"):
            continue

        psets = ifcopenshell.util.element.get_psets(bauteil)
        if "GoBau_Menge" not in psets:
            continue

        menge = psets["GoBau_Menge"]
        struktur = psets.get("GoBau_Struktur", {})

        zeile = {
            "datei": pfad.name,
            "fachmodell": fachmodell,
            "global_id": bauteil.GlobalId,
            "klasse": bauteil.is_a(),
            "name": bauteil.Name,
        }
        for stufe in STUFEN:
            wert = struktur.get(stufe)
            if isinstance(wert, str):
                wert = wert.strip()
            zeile[stufe.lower()] = wert
        for ifc_name, spalte in MENGEN.items():
            zeile[spalte] = menge.get(ifc_name)

        zeilen.append(zeile)

    spalten = ["datei", "fachmodell", "global_id", "klasse", "name"]
    spalten += [stufe.lower() for stufe in STUFEN] + list(MENGEN.values())
    return pd.DataFrame(zeilen, columns=spalten)


def lese_alle_ifc(ordner):
    """Liest alle IFC-Dateien eines Ordners und haengt die Tabellen untereinander."""
    tabellen = [lese_ifc(pfad) for pfad in sorted(Path(ordner).glob("*.ifc"))]
    return pd.concat(tabellen, ignore_index=True)


if __name__ == "__main__":
    # Test im Terminal: python -m importers.ifc_reader
    bauteile = lese_alle_ifc("daten")

    print("Anzahl Bauteile pro Datei:")
    print(bauteile.groupby("datei").size().to_string())
    print("Total:", len(bauteile))

    print("\nMengen pro Stufe_4 / Stufe_5:")
    mengen = bauteile.groupby(["stufe_4", "stufe_5"], dropna=False)[list(MENGEN.values())].sum()
    print(mengen.round(2).to_string())
