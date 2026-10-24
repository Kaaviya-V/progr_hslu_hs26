"""Ersatzquellen: fehlende neutrale Felder aus der IFC-Hierarchie ergaenzen.

So funktioniert das Programm auch mit Modellen ohne GoBau-Property-Sets.
Reihenfolge je Feld: zuerst der Wert aus den Einstellungen (z.B. GoBau_Struktur),
fehlt er, die Ersatzquelle aus dem IFC:

    bereich        Name des obersten uebergeordneten IfcRoadPart      (ifc_bereich)
    bauteilgruppe  Name des direkt uebergeordneten IfcRoadPart       (ifc_bauteilgruppe)
    typ_schicht    Randsteine: Name der IfcElementAssembly           (ifc_baugruppe)
                   sonst (Schichten usw.): Bauteilname               (name)
    element        Bauteilname                                       (name)

Die Spalte ersatzfelder zeigt je Bauteil, welche Felder aus einer Ersatzquelle stammen,
damit man sieht, wo das Modell keine eigene Angabe hatte.
"""

import pandas as pd


def _ersatz_typ_schicht(bauteil):
    """Randsteine liegen in einer IfcElementAssembly (Typ), alle anderen nehmen den Bauteilnamen."""
    if pd.notna(bauteil["ifc_baugruppe"]):
        return bauteil["ifc_baugruppe"]
    return bauteil["name"]


def ersatzwerte(bauteile):
    """Gibt fuer jedes neutrale Feld die Ersatzwerte aus der IFC-Hierarchie zurueck."""
    return pd.DataFrame({
        "bereich": bauteile["ifc_bereich"],
        "bauteilgruppe": bauteile["ifc_bauteilgruppe"],
        "typ_schicht": bauteile.apply(_ersatz_typ_schicht, axis=1),
        "element": bauteile["name"],
    }, index=bauteile.index)


def ergaenze_felder(bauteile, felder=("bereich", "bauteilgruppe", "typ_schicht", "element")):
    """Fuellt leere neutrale Felder mit den Ersatzwerten und merkt sich, welche ersetzt wurden.

    felder: welche Felder ergaenzt werden duerfen (Standard: alle vier).
    """
    bauteile = bauteile.copy()
    ersatz = ersatzwerte(bauteile)
    ersetzt = pd.Series("", index=bauteile.index)

    for feld in felder:
        fehlt = bauteile[feld].isna() & ersatz[feld].notna()
        bauteile.loc[fehlt, feld] = ersatz.loc[fehlt, feld]
        ersetzt[fehlt] += ", " + feld

    bauteile["ersatzfelder"] = ersetzt.str.lstrip(", ").replace("", None)
    return bauteile


if __name__ == "__main__":
    # Test im Terminal: python -m importers.sources
    from calculation.costs import berechne_kosten, berechne_total
    from calculation.mapping import ordne_zu
    from importers.ebkp_reader import lese_ebkp_liste
    from importers.ifc_reader import lese_alle_ifc

    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 60)
    positionen, zuordnung, einstellungen = lese_ebkp_liste("daten/eBKP-T_Preisliste_Zuordnung.xlsx")

    def auswerten(titel, bauteile):
        zugeordnet, meldungen = ordne_zu(bauteile, zuordnung, positionen)
        kosten, _, _ = berechne_kosten(zugeordnet, positionen)
        print(f"\n=== {titel} ===")
        total = f"{berechne_total(kosten):,.2f}".replace(",", "'")
        print(f"zugeordnet {zugeordnet['pos_id'].notna().sum()}/{len(zugeordnet)}, Total CHF {total}")
        if len(meldungen):
            print(meldungen.groupby(["schwere", "pruefung"]).size().to_string())
        return zugeordnet

    # lese_alle_ifc ruft ergaenze_felder schon selbst auf
    mit_gobau = lese_alle_ifc("daten", einstellungen)
    referenz = auswerten("1 Mit GoBau_Struktur (Ersatz nur, wo ein Wert fehlt)", mit_gobau)
    print("Felder aus Ersatzquelle:", mit_gobau["ersatzfelder"].value_counts().to_dict())

    # Ohne GoBau_Struktur: Property-Set absichtlich falsch benennen -> alle Felder aus dem IFC
    ohne = {"felder": {f: ("GIBT_ES_NICHT", p) for f, (_, p) in einstellungen["felder"].items()},
            "mengen": einstellungen["mengen"]}
    ohne_gobau = lese_alle_ifc("daten", ohne)
    ergebnis = auswerten("2 OHNE GoBau_Struktur, nur Ersatzquellen", ohne_gobau)
    print("Felder aus Ersatzquelle:", ohne_gobau["ersatzfelder"].value_counts().to_dict())

    # Wo klappt es nicht? Vergleich mit der Referenz-Pos-ID je Bauteil
    vergleich = referenz[["guid", "fachmodell", "klasse", "name", "pos_id"]].merge(
        ergebnis[["guid", "typ_schicht", "element", "treffer_pos_ids"]], on="guid")
    falsch = vergleich[vergleich["pos_id"] != vergleich["treffer_pos_ids"]]
    print("\nRichtig je Fachmodell (ohne GoBau):")
    richtig = (vergleich["pos_id"] == vergleich["treffer_pos_ids"]).groupby(vergleich["fachmodell"])
    print(pd.DataFrame({"richtig": richtig.sum(), "total": richtig.size()}).T.to_string())
    print("\nAbweichungen (je Kombination einmal):")
    print(falsch.drop_duplicates(["klasse", "typ_schicht", "pos_id", "treffer_pos_ids"])
          .drop(columns="guid").to_string())
