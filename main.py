"""KOSTRA – Weboberflaeche (Streamlit).

Start im Terminal: streamlit run main.py

Streamlit fuehrt dieses Skript bei JEDER Bedienung (Upload, Klick) von oben nach unten neu aus.
Was teuer ist (IFC lesen), wird deshalb im Session State gespeichert und nur neu berechnet,
wenn sich die hochgeladenen Dateien oder die Einstellungen aendern.
st.stop() beendet den Durchlauf: So werden spaetere Schritte gesperrt, solange Fehler bestehen.

Hier steht keine Fachlogik, nur Anzeige und Aufrufe der Module.
"""

from io import BytesIO

import streamlit as st

from calculation.costs import berechne_kosten, berechne_total
from calculation.mapping import ordne_zu
from export.excel_writer import schreibe_auffaelligkeiten, schreibe_kostenschaetzung
from export.ifc_writer import oeffne_hochgeladene_ifc, schreibe_gesamtmodell
from importers.ebkp_reader import lese_ebkp_liste
from importers.ifc_reader import EINSTELLUNGEN_STANDARD, lese_hochgeladene_ifc
from validation.list_checks import pruefe_liste
from validation.model_checks import FEHLER, hat_fehler, pruefe_modell
from visualization.charts import diagramm_kosten_je_gruppe

EXCEL_TYP = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

st.set_page_config(page_title="KOSTRA", layout="wide")
st.title("KOSTRA – vom Modell zur Kostenschätzung")


def zeige_meldungen(meldungen, titel):
    """Zeigt die Anzahl Fehler/Hinweise und die Meldungen in einer aufklappbaren Tabelle."""
    fehler = (meldungen["schwere"] == FEHLER).sum()
    hinweise = len(meldungen) - fehler
    if fehler:
        st.error(f"{titel}: {fehler} Fehler, {hinweise} Hinweise")
    elif hinweise:
        st.warning(f"{titel}: keine Fehler, {hinweise} Hinweise")
    else:
        st.success(f"{titel}: keine Meldungen")
    if len(meldungen):
        with st.expander("Meldungen anzeigen", expanded=bool(fehler)):
            st.dataframe(meldungen.dropna(axis=1, how="all"), hide_index=True, width="stretch")


def signatur(dateien):
    """Erkennungsmerkmal der hochgeladenen Dateien (Name und Groesse), um Aenderungen zu bemerken."""
    return tuple((datei.name, datei.size) for datei in dateien)


# ---------------------------------------------------------------- 1 IFC einlesen
st.header("1 · IFC-Modelle einlesen")
ifc_dateien = st.file_uploader("IFC-Dateien (Fachmodelle)", type="ifc", accept_multiple_files=True)
if not ifc_dateien:
    st.info("Bitte eine oder mehrere IFC-Dateien hochladen.")
    st.stop()

# Einstellungen kommen aus der eBKP-T-Liste (Schritt 4); bis dahin gilt der Standard (GoBau)
einstellungen = st.session_state.get("einstellungen", EINSTELLUNGEN_STANDARD)
schluessel = (signatur(ifc_dateien), str(einstellungen))
if st.session_state.get("ifc_schluessel") != schluessel:
    with st.spinner("IFC-Dateien werden gelesen …"):
        bauteile = lese_hochgeladene_ifc(ifc_dateien, einstellungen)
        st.session_state["bauteile"] = bauteile
        st.session_state["modell_meldungen"] = pruefe_modell(bauteile)
        st.session_state["ifc_schluessel"] = schluessel

bauteile = st.session_state["bauteile"]
modell_meldungen = st.session_state["modell_meldungen"]

spalte1, spalte2 = st.columns([1, 3])
spalte1.metric("Bauteile", len(bauteile))
spalte2.dataframe(
    bauteile.groupby("fachmodell").size().rename("Bauteile").to_frame().T,
    width="stretch",
)

# ---------------------------------------------------------------- 2 + 3 Modell pruefen, Entscheid
st.header("2 · Modell prüfen")
zeige_meldungen(modell_meldungen, "Modellprüfung")
if len(modell_meldungen):
    st.download_button(
        "Betroffene Bauteile als Excel herunterladen",
        schreibe_auffaelligkeiten({"Modellprüfung": modell_meldungen}, bauteile),
        file_name="KOSTRA_Modellpruefung.xlsx",
        mime=EXCEL_TYP,
    )
if hat_fehler(modell_meldungen):
    st.error("Das Modell hat Fehler. Bitte im Modell korrigieren und die IFC-Dateien neu hochladen.")
    st.stop()

# ---------------------------------------------------------------- 4 eBKP-T-Liste
st.header("3 · eBKP-T-Liste laden und prüfen")
liste_datei = st.file_uploader("eBKP-T-Liste (Excel)", type="xlsx")
if liste_datei is None:
    st.info("Bitte die eBKP-T-Liste hochladen.")
    st.stop()

positionen, zuordnung, liste_einstellungen = lese_ebkp_liste(BytesIO(liste_datei.getvalue()))
liste_meldungen = pruefe_liste(positionen, zuordnung, liste_einstellungen)
st.write(f"{len(positionen)} Positionen, {len(zuordnung)} Regeln")
zeige_meldungen(liste_meldungen, "Listenprüfung")
if hat_fehler(liste_meldungen):
    st.error("Die Liste hat Fehler. Bitte in Excel korrigieren und neu hochladen.")
    st.stop()

# Liste gibt andere Einstellungen vor als beim Einlesen -> IFC damit nochmals lesen (Neustart des Skripts)
if liste_einstellungen != einstellungen:
    st.session_state["einstellungen"] = liste_einstellungen
    st.rerun()

# ---------------------------------------------------------------- 5 Zuordnen
st.header("4 · Zuordnen")
zugeordnet, zuordnungs_meldungen = ordne_zu(bauteile, zuordnung, positionen)
st.write(f"{zugeordnet['pos_id'].notna().sum()} von {len(zugeordnet)} Bauteilen genau einer Position zugeordnet")
zeige_meldungen(zuordnungs_meldungen, "Zuordnung")
if hat_fehler(zuordnungs_meldungen):
    st.error("Es gibt Konflikte (Bauteile mit mehreren Positionen). Bitte die Regeln im Blatt «Zuordnung» anpassen.")
    st.stop()

# ---------------------------------------------------------------- 6 Berechnen
st.header("5 · Kosten")
kosten, bauteilkosten, mengen_meldungen = berechne_kosten(zugeordnet, positionen)
total = f"{berechne_total(kosten):,.2f}".replace(",", "'")
st.metric("Total exkl. MwSt.", f"CHF {total}")
zeige_meldungen(mengen_meldungen, "Berechnung")
st.dataframe(
    kosten.drop(columns=["ebkp_code"]),
    hide_index=True,
    width="stretch",
    column_config={
        "menge": st.column_config.NumberColumn("Menge", format="%.3f"),
        "einheitspreis": st.column_config.NumberColumn("Einheitspreis (CHF)", format="%.2f"),
        "kosten": st.column_config.NumberColumn("Kosten (CHF)", format="%.2f"),
        "anteil": st.column_config.ProgressColumn("Anteil", format="percent", min_value=0, max_value=1),
    },
)

st.pyplot(diagramm_kosten_je_gruppe(kosten))

# ---------------------------------------------------------------- 7 Exportieren
st.header("6 · Exportieren")
alle_meldungen = {
    "Modellprüfung": modell_meldungen,
    "Listenprüfung": liste_meldungen,
    "Zuordnung": zuordnungs_meldungen,
    "Berechnung": mengen_meldungen,
}
st.download_button(
    "Kostenschätzung als Excel herunterladen",
    schreibe_kostenschaetzung(
        kosten, bauteilkosten, alle_meldungen, [d.name for d in ifc_dateien], liste_datei.name
    ),
    file_name="KOSTRA_Kostenschaetzung.xlsx",
    mime=EXCEL_TYP,
    type="primary",
)

# Gesamtmodell: dauert einige Sekunden und gibt eine grosse Datei, darum erst auf Knopfdruck.
# Das Ergebnis bleibt im Session State, solange IFC-Dateien und Liste gleich bleiben.
st.subheader("IFC-Gesamtmodell")
st.caption("Alle Fachmodelle in einer Datei, jedes Bauteil mit Pset_KOSTRA (Pos-ID, Menge, Kosten, Status).")
gesamt_schluessel = (st.session_state["ifc_schluessel"], liste_datei.name, liste_datei.size)
gespeichert = st.session_state.get("gesamtmodell")
if gespeichert is None or gespeichert[0] != gesamt_schluessel:
    if st.button("Gesamtmodell erstellen"):
        with st.spinner("Gesamtmodell wird erstellt …"):
            inhalt = schreibe_gesamtmodell(oeffne_hochgeladene_ifc(ifc_dateien), bauteilkosten, positionen)
        st.session_state["gesamtmodell"] = (gesamt_schluessel, inhalt)
        st.rerun()
else:
    st.download_button(
        f"Gesamtmodell herunterladen ({len(gespeichert[1]) / 1e6:.0f} MB)",
        gespeichert[1],
        file_name="KOSTRA_Gesamtmodell.ifc",
        mime="application/x-step",
    )
