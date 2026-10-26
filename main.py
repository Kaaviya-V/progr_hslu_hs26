"""KOSTRA – Weboberflaeche Version 2 (Streamlit).

Start im Terminal: streamlit run main.py
Version 1 (eingefroren): Z_main_v1.py

Aufbau:
1. Rechnen: alle Schritte nacheinander; ein Fehler sperrt die folgenden Schritte.
   Teure Ergebnisse bleiben im Session State und werden nur neu berechnet, wenn sich
   die hochgeladenen Dateien aendern (Filter und Tab-Wechsel bleiben so schnell).
2. Seitenleiste: Uploads und die 7 Schritte mit Status ✓ / ⚠ / ✗.
3. Hauptbereich: 5 Kennzahlen, darunter Tabs Pruefung, Kosten, Bauteile, Diagramm, Export.

Hier steht keine Fachlogik, nur Ablauf, Anzeige und Aufrufe der Module.
"""

from io import BytesIO

import streamlit as st

from calculation.costs import berechne_kosten, berechne_total
from calculation.mapping import ordne_zu
from export.excel_writer import sammle_meldungen, schreibe_auffaelligkeiten, schreibe_kostenschaetzung
from export.ifc_writer import oeffne_hochgeladene_ifc, schreibe_gesamtmodell
from importers.ebkp_reader import lese_ebkp_liste
from importers.ifc_reader import EINSTELLUNGEN_STANDARD, lese_hochgeladene_ifc
from validation.list_checks import pruefe_liste
from validation.model_checks import FEHLER, hat_fehler, pruefe_modell
from visualization.charts import chf, diagramm_kosten_je_gruppe
from visualization.tabellen import (
    FEHLT, KOSTEN_SPALTEN, OFFEN, OK, anzahl_text, bauteile_tabelle, kosten_tabelle,
    meldungen_tabelle, status,
)

EXCEL_TYP = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SCHRITTE = ["IFC einlesen", "Modell prüfen", "Entscheid", "eBKP-T-Liste prüfen",
            "Zuordnen", "Berechnen", "Exportieren"]

st.set_page_config(layout="wide", page_title="KOSTRA")
zustand = st.session_state


def signatur(dateien):
    """Erkennungsmerkmal hochgeladener Dateien (Name und Groesse), um Aenderungen zu bemerken."""
    if dateien is None:
        return None
    if not isinstance(dateien, list):
        dateien = [dateien]
    return tuple((d.name, d.size) for d in dateien)


# ================================================================== Seitenleiste: Uploads
with st.sidebar:
    st.title("KOSTRA")
    st.caption("vom Modell zur Kostenschätzung")
    ifc_dateien = st.file_uploader("IFC-Modelle", type="ifc", accept_multiple_files=True)
    liste_datei = st.file_uploader("eBKP-T-Liste", type="xlsx")
    st.divider()
    schritte_platz = st.container()     # wird unten gefuellt, wenn alle Ergebnisse bekannt sind

# ================================================================== 1 Rechnen
schritt = {name: (OFFEN, "") for name in SCHRITTE}   # Name -> (Symbol, kurzer Text)
lesefehler = []
meldungen_je_schritt = {}
bauteile = positionen = zuordnung = kosten = bauteilkosten = None

# --- 1 IFC einlesen (nur neu, wenn Dateien oder Einstellungen aendern)
if ifc_dateien:
    einstellungen = zustand.get("einstellungen", EINSTELLUNGEN_STANDARD)
    ifc_schluessel = (signatur(ifc_dateien), str(einstellungen))
    if zustand.get("ifc_schluessel") != ifc_schluessel:
        zustand["ifc_schluessel"] = ifc_schluessel
        try:
            with st.spinner("IFC-Dateien werden gelesen …"):
                zustand["bauteile"] = lese_hochgeladene_ifc(ifc_dateien, einstellungen)
            zustand["modell_meldungen"] = pruefe_modell(zustand["bauteile"])
            zustand["ifc_fehler"] = None
        except ValueError as fehler:
            zustand["bauteile"] = zustand["modell_meldungen"] = None
            zustand["ifc_fehler"] = str(fehler)

    bauteile = zustand["bauteile"]
    if zustand["ifc_fehler"]:
        lesefehler.append(zustand["ifc_fehler"])
        schritt["IFC einlesen"] = (FEHLT, "Datei nicht lesbar")
    else:
        schritt["IFC einlesen"] = (OK, f"{len(bauteile)} Bauteile")

# --- 2 Modell pruefen, 3 Entscheid
if bauteile is not None:
    meldungen_je_schritt["Modellprüfung"] = zustand["modell_meldungen"]
    schritt["Modell prüfen"] = (status(zustand["modell_meldungen"]), anzahl_text(zustand["modell_meldungen"]))
    modell_gesperrt = hat_fehler(zustand["modell_meldungen"])
    schritt["Entscheid"] = (FEHLT, "gesperrt – Modell korrigieren") if modell_gesperrt else (OK, "freigegeben")
else:
    modell_gesperrt = True

# --- 4 Liste lesen und pruefen, 5 Zuordnen, 6 Berechnen (nur neu, wenn IFC oder Liste aendern)
if liste_datei is not None and not modell_gesperrt:
    rechen_schluessel = (zustand["ifc_schluessel"], signatur(liste_datei))
    if zustand.get("rechen_schluessel") != rechen_schluessel:
        zustand["rechen_schluessel"] = rechen_schluessel
        ergebnis = {"liste_fehler": None}
        try:
            positionen, zuordnung, liste_einstellungen = lese_ebkp_liste(BytesIO(liste_datei.getvalue()))
            ergebnis.update(positionen=positionen, zuordnung=zuordnung,
                            liste_meldungen=pruefe_liste(positionen, zuordnung, liste_einstellungen))
            if not hat_fehler(ergebnis["liste_meldungen"]):
                # Liste gibt andere Einstellungen vor -> IFC damit nochmals lesen (Neustart)
                if liste_einstellungen != zustand.get("einstellungen", EINSTELLUNGEN_STANDARD):
                    zustand["einstellungen"] = liste_einstellungen
                    del zustand["rechen_schluessel"]
                    st.rerun()
                zugeordnet, ergebnis["zuordnungs_meldungen"] = ordne_zu(bauteile, zuordnung, positionen)
                ergebnis["zugeordnet"] = zugeordnet
                if not hat_fehler(ergebnis["zuordnungs_meldungen"]):
                    (ergebnis["kosten"], ergebnis["bauteilkosten"],
                     ergebnis["mengen_meldungen"]) = berechne_kosten(zugeordnet, positionen)
        except ValueError as fehler:
            ergebnis["liste_fehler"] = str(fehler)
        zustand["ergebnis"] = ergebnis

    ergebnis = zustand["ergebnis"]
    if ergebnis["liste_fehler"]:
        lesefehler.append(ergebnis["liste_fehler"])
        schritt["eBKP-T-Liste prüfen"] = (FEHLT, "Datei nicht lesbar")
    else:
        positionen, zuordnung = ergebnis["positionen"], ergebnis["zuordnung"]
        for name, schluessel, titel in [("eBKP-T-Liste prüfen", "liste_meldungen", "Listenprüfung"),
                                        ("Zuordnen", "zuordnungs_meldungen", "Zuordnung"),
                                        ("Berechnen", "mengen_meldungen", "Berechnung")]:
            if schluessel in ergebnis:
                meldungen_je_schritt[titel] = ergebnis[schluessel]
                schritt[name] = (status(ergebnis[schluessel]), anzahl_text(ergebnis[schluessel]))
        bauteile = ergebnis.get("bauteilkosten", ergebnis.get("zugeordnet", bauteile))
        kosten, bauteilkosten = ergebnis.get("kosten"), ergebnis.get("bauteilkosten")
        if kosten is not None:
            schritt["Exportieren"] = (OK, "bereit")

# ================================================================== 2 Seitenleiste: Schritte
with schritte_platz:
    for nummer, name in enumerate(SCHRITTE, start=1):
        symbol, text = schritt[name]
        st.markdown(f"{symbol} &nbsp; **{nummer} {name}**  \n"
                    f"<span style='opacity:0.6;font-size:0.85em'>{text}</span>", unsafe_allow_html=True)

# ================================================================== 3 Hauptbereich
for text in lesefehler:
    st.error(text)
if not ifc_dateien:
    st.info("Links die IFC-Modelle und die eBKP-T-Liste hochladen.")
    st.stop()

# --- Kennzahlen
alle_meldungen = sammle_meldungen(meldungen_je_schritt)
anzahl_fehler = int((alle_meldungen["schwere"] == FEHLER).sum())
anzahl_hinweise = len(alle_meldungen) - anzahl_fehler

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Bauteile", len(bauteile) if bauteile is not None else "–", border=True)
if positionen is not None:
    k2.metric("Positionen", len(positionen), delta=f"{len(zuordnung)} Regeln",
              delta_color="off", delta_arrow="off", border=True)
else:
    k2.metric("Positionen", "–", border=True)
if bauteile is not None and "pos_id" in bauteile.columns:
    k3.metric("Zuordnung", f"{bauteile['pos_id'].notna().mean():.0%}", border=True)
else:
    k3.metric("Zuordnung", "–", border=True)
k4.metric("Meldungen", f"{anzahl_fehler} / {anzahl_hinweise}", help="Fehler / Hinweise", border=True)
k5.metric("Total CHF", chf(berechne_total(kosten)) if kosten is not None else "–",
          help="exkl. MwSt.", border=True)

NOCH_NICHT = "Erst verfügbar, wenn IFC-Modelle und eBKP-T-Liste ohne Fehler geprüft und zugeordnet sind."
tab_pruefung, tab_kosten, tab_bauteile, tab_diagramm, tab_export = st.tabs(
    ["Prüfung", "Kosten je Position", "Bauteile", "Diagramm", "Export"])

# --- Tab Pruefung: je Pruefung eine kompakte Kachel, darunter alle Meldungen
with tab_pruefung:
    kacheln = st.columns(4)
    for spalte, titel in zip(kacheln, ["Modellprüfung", "Listenprüfung", "Zuordnung", "Berechnung"]):
        tabelle = meldungen_je_schritt.get(titel)
        with spalte.container(border=True):
            st.markdown(f"**{status(tabelle)} {titel}**  \n"
                        f"<span style='opacity:0.6'>{anzahl_text(tabelle)}</span>", unsafe_allow_html=True)

    if len(alle_meldungen):
        st.dataframe(meldungen_tabelle(alle_meldungen), hide_index=True, width="stretch",
                     column_config={"Meldung": st.column_config.TextColumn(width="large")})
        st.download_button("Betroffene Bauteile als Excel",
                           schreibe_auffaelligkeiten(meldungen_je_schritt, zustand.get("bauteile")),
                           file_name="KOSTRA_Auffaelligkeiten.xlsx", mime=EXCEL_TYP)
    else:
        st.caption("Keine Hinweise oder Fehler.")

# --- Tab Kosten je Position: Filter Gruppe, Suche, sortiert nach Kosten
with tab_kosten:
    if kosten is None:
        st.info(NOCH_NICHT)
    else:
        filter1, filter2 = st.columns([1, 2])
        gruppe = filter1.selectbox("Gruppe", ["Alle"] + sorted(kosten["gruppe"].dropna().unique()))
        suche = filter2.text_input("Suche", placeholder="Pos-ID oder Bezeichnung")
        st.dataframe(kosten_tabelle(kosten, None if gruppe == "Alle" else gruppe, suche),
                     column_config=KOSTEN_SPALTEN, hide_index=True, width="stretch", height=600)

# --- Tab Bauteile
with tab_bauteile:
    if bauteile is None:
        st.info("Erst verfügbar, wenn die IFC-Modelle gelesen sind.")
    else:
        st.dataframe(bauteile_tabelle(bauteile), hide_index=True, width="stretch", height=600)

# --- Tab Diagramm
with tab_diagramm:
    if kosten is None:
        st.info(NOCH_NICHT)
    else:
        st.plotly_chart(diagramm_kosten_je_gruppe(kosten), theme=None, width="stretch")

# --- Tab Export: zwei Kacheln
with tab_export:
    if kosten is None:
        st.info(NOCH_NICHT)
    else:
        excel_kachel, ifc_kachel = st.columns(2)

        with excel_kachel.container(border=True):
            st.markdown("**Kostenschätzung (Excel)**")
            st.caption("Zusammenfassung, Kosten je Position, Bauteilliste, Auffälligkeiten")
            if zustand.get("excel_schluessel") != zustand["rechen_schluessel"]:
                zustand["excel"] = schreibe_kostenschaetzung(
                    kosten, bauteilkosten, meldungen_je_schritt, [d.name for d in ifc_dateien], liste_datei.name)
                zustand["excel_schluessel"] = zustand["rechen_schluessel"]
            st.download_button("Excel herunterladen", zustand["excel"], file_name="KOSTRA_Kostenschaetzung.xlsx",
                               mime=EXCEL_TYP, type="primary", width="stretch")

        # Gesamtmodell erst auf Knopfdruck (einige Sekunden, grosse Datei)
        with ifc_kachel.container(border=True):
            st.markdown("**Gesamtmodell (IFC)**")
            st.caption("Alle Fachmodelle in einer Datei, jedes Bauteil mit Pset_KOSTRA")
            gespeichert = zustand.get("gesamtmodell")
            if gespeichert is None or gespeichert[0] != zustand["rechen_schluessel"]:
                if st.button("Gesamtmodell erstellen", width="stretch"):
                    with st.spinner("Gesamtmodell wird erstellt …"):
                        inhalt = schreibe_gesamtmodell(oeffne_hochgeladene_ifc(ifc_dateien), bauteilkosten, positionen)
                    zustand["gesamtmodell"] = (zustand["rechen_schluessel"], inhalt)
                    st.rerun()
            else:
                st.download_button(f"IFC herunterladen ({len(gespeichert[1]) / 1e6:.0f} MB)", gespeichert[1],
                                   file_name="KOSTRA_Gesamtmodell.ifc", mime="application/x-step", width="stretch")
