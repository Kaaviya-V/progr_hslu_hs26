"""Hilfsskript: Liste aller Stufe_6-Werte als Grundlage fuer die Preisliste.

Ausfuehren im Terminal: python bauteiltypen_liste.py
Ergebnis: daten/bauteiltypen.xlsx
"""

from importers.ifc_reader import lese_alle_ifc

bauteile = lese_alle_ifc("daten")

# Pro Kombination aus Stufe_5 und Stufe_6: Anzahl Bauteile und Summen der Mengen
liste = (
    bauteile.groupby(["stufe_5", "stufe_6"])
    .agg(
        anzahl_bauteile=("global_id", "count"),
        laenge_m=("laenge", "sum"),
        flaeche_m2=("flaeche", "sum"),
        volumen_m3=("volumen", "sum"),
    )
    .round(2)
    .reset_index()
)

liste.to_excel("daten/bauteiltypen.xlsx", index=False)
print(f"{len(liste)} Zeilen gespeichert in daten/bauteiltypen.xlsx")
