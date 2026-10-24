"""Mengen aus der Geometrie (3. Mengenquelle, nur wenn GoBau_Menge und Qto fehlen).

Je Bauteil wird das Dreiecksnetz der Darstellung «Body» berechnet. Daraus:
- volumen:  Volumen des geschlossenen Netzes
- flaeche:  Grundrissflaeche (Projektion von oben), wie GoBau «Fläche»
- laenge:   Ausdehnung entlang der Hauptachse (Richtung, in der das Bauteil am laengsten ist).
            Im Vergleich mit GoBau: 80-85 % der Bauteile innerhalb 2 %, 95-100 % innerhalb 10 %.
            Bei stark gebogenen Bauteilen etwas zu kurz (Sehne statt Bogen).
- anzahl:   1 (jedes IFC-Bauteil ist ein Stueck)

Achtung Landeskoordinaten: Die Modelle liegen bei X ~ 2'681'000 m. Mit so grossen Zahlen
verliert die Volumenformel Nachkommastellen (Volumen teils doppelt so gross!). Darum wird
jedes Bauteil vor der Berechnung zum Nullpunkt verschoben; am Volumen aendert das nichts.

Geometrie-Mengen sind Naeherungen und werden als Hinweis gemeldet (siehe model_checks).
"""

import multiprocessing

import ifcopenshell.geom
import ifcopenshell.util.shape
import numpy as np
import pandas as pd

QUELLE_GEOMETRIE = "Geometrie"
GEO_SPALTEN = ["guid", "anzahl", "laenge", "flaeche", "volumen"]


def _volumen(geometrie):
    """Volumen eines geschlossenen Dreiecksnetzes, zuerst zum Nullpunkt verschoben."""
    punkte = np.array(geometrie.verts).reshape(-1, 3)
    punkte = punkte - punkte.mean(axis=0)                # weg von den Landeskoordinaten
    dreiecke = np.array(geometrie.faces).reshape(-1, 3)
    a, b, c = punkte[dreiecke[:, 0]], punkte[dreiecke[:, 1]], punkte[dreiecke[:, 2]]
    # Jedes Dreieck bildet mit dem Nullpunkt einen Tetraeder; die Summe ergibt das Volumen
    return abs(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6)


def _laenge(geometrie):
    """Laenge entlang der Hauptachse des Bauteils.

    Die Hauptachse ist die Richtung, in der die Punkte am weitesten streuen
    (Hauptkomponentenanalyse mit np.linalg.svd). Die Laenge ist der Abstand
    zwischen dem ersten und dem letzten Punkt entlang dieser Richtung.
    """
    punkte = np.array(geometrie.verts).reshape(-1, 3)
    punkte = punkte - punkte.mean(axis=0)
    hauptachse = np.linalg.svd(punkte, full_matrices=False)[2][0]
    entlang = punkte @ hauptachse
    return entlang.max() - entlang.min()


def berechne_geometrie_mengen(modell, guids=None):
    """Berechnet die vier Mengen aus der Geometrie.

    modell: geoeffnetes IFC-Modell
    guids:  nur diese Bauteile berechnen (None = alle); die Berechnung dauert ca. 0.1 s pro Bauteil
    """
    bauteile = [modell.by_guid(g) for g in guids] if guids is not None else modell.by_type("IfcElement")
    bauteile = [b for b in bauteile if b.Representation is not None]
    if not bauteile:
        return pd.DataFrame(columns=GEO_SPALTEN)

    einstellungen = ifcopenshell.geom.settings()
    einstellungen.set("use-world-coords", True)   # Grundriss braucht die echte Lage (oben = Z)
    einstellungen.set("weld-vertices", True)      # gleiche Punkte zusammenlegen -> geschlossenes Netz

    zeilen = []
    iterator = ifcopenshell.geom.iterator(einstellungen, modell, multiprocessing.cpu_count(), include=bauteile)
    if iterator.initialize():
        while True:
            form = iterator.get()
            geometrie = form.geometry
            zeilen.append({
                "guid": modell.by_id(form.id).GlobalId,
                "anzahl": 1,
                "laenge": _laenge(geometrie),
                "flaeche": ifcopenshell.util.shape.get_footprint_area(geometrie),
                "volumen": _volumen(geometrie),
            })
            if not iterator.next():
                break
    return pd.DataFrame(zeilen, columns=GEO_SPALTEN)


def ergaenze_mengen(bauteile, modell):
    """Ergaenzt die Mengen der Bauteile ohne zuverlaessige Mengenquelle aus der Geometrie.

    Nur Bauteile ganz ohne Mengenquelle (kein GoBau_Menge / Qto) werden berechnet.
    Einzelne fehlende Mengen (z.B. Nagelwand ohne Fläche) bleiben leer und werden gemeldet,
    damit nicht still eine unpassende Geometrie-Menge (Grundriss einer Wand) verwendet wird.
    """
    ohne = bauteile["mengenquelle"].isna()
    if not ohne.any():
        return bauteile        # Normalfall mit GoBau: keine Geometrie noetig, keine Wartezeit

    geo = berechne_geometrie_mengen(modell, list(bauteile.loc[ohne, "guid"])).set_index("guid")
    bauteile = bauteile.copy()
    for menge in ["anzahl", "laenge", "flaeche", "volumen"]:
        werte = bauteile.loc[ohne, "guid"].map(geo[menge])
        bauteile.loc[ohne, menge] = werte
    bauteile.loc[ohne & bauteile["guid"].isin(geo.index), "mengenquelle"] = QUELLE_GEOMETRIE
    return bauteile


if __name__ == "__main__":
    # Test im Terminal: python -m importers.geometry
    # Vergleicht die Geometrie-Mengen je IFC-Klasse mit GoBau_Menge (Anteil innerhalb 2 %)
    import time
    from pathlib import Path

    import ifcopenshell

    from importers.ifc_reader import IGNORIERTE_KLASSEN, lese_ifc

    pd.set_option("display.width", 200)
    tabellen = []
    start = time.time()
    for pfad in sorted(Path("daten").glob("*.ifc")):
        modell = ifcopenshell.open(str(pfad))
        gobau = lese_ifc(pfad).set_index("guid")
        guids = [g for g in gobau.index if modell.by_guid(g).is_a() not in IGNORIERTE_KLASSEN]
        geo = berechne_geometrie_mengen(modell, guids).set_index("guid")
        tabellen.append(gobau[["klasse", "laenge", "flaeche", "volumen"]].join(geo, rsuffix="_geo"))
        print(f"{pfad.name:25} {len(geo):4} Bauteile")
    print(f"Zeit: {time.time() - start:.0f} s")

    alle = pd.concat(tabellen)

    def anteil_ok(gruppe, menge):
        """Anteil der Bauteile, bei denen Geometrie und GoBau weniger als 2 % abweichen."""
        mit_wert = gruppe[gruppe[menge] > 0]
        if mit_wert.empty:
            return None
        return ((mit_wert[f"{menge}_geo"] / mit_wert[menge] - 1).abs() < 0.02).mean()

    vergleich = alle.groupby("klasse").apply(lambda g: pd.Series({
        "bauteile": len(g),
        "laenge_ok": anteil_ok(g, "laenge"),
        "flaeche_ok": anteil_ok(g, "flaeche"),
        "volumen_ok": anteil_ok(g, "volumen"),
    }), include_groups=False)
    print("\nAnteil Bauteile mit < 2 % Abweichung zu GoBau (leer = GoBau hat diese Menge nicht):")
    print(vergleich.to_string(formatters={s: "{:.0%}".format for s in ["laenge_ok", "flaeche_ok", "volumen_ok"]}))
