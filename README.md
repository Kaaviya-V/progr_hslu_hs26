# KOSTRA – vom Modell zur Kostenschätzung

Semesterprojekt im Modul *Digital Twin Programmieren* (HSLU, Digital Construction, HS26).

KOSTRA ist eine Web-Anwendung (Python, Streamlit). Sie liest Strassenmodelle im Format IFC 4.3 ein,
prüft sie und ordnet die Bauteile über Regeln den Positionen einer eBKP-T-Liste (Excel) zu.
Daraus berechnet sie Mengen und Kosten. Am Ende entstehen eine Excel-Kostenschätzung und auf Wunsch
ein IFC-Gesamtmodell, in dem jedes Bauteil seine Position und seine Kosten trägt.
**Jede Zahl lässt sich über die GUID auf das Bauteil zurückverfolgen.**

## Ablauf

1. **IFC einlesen:** Bauteile mit GUID, Klasse, Hierarchie, Bezeichnungen und Mengen
2. **Modell prüfen:** Pflichtangaben, Mengen, doppelte GUIDs, mögliche Duplikate
3. **Entscheid:** Fehler sperren den nächsten Schritt, Hinweise nicht. Die betroffenen Bauteile lassen sich als Excel herunterladen.
4. **eBKP-T-Liste laden und prüfen:** Blätter, Spalten, Pos-IDs, Mengenarten, Preise
5. **Zuordnen:** Regeln anwenden; Bauteile ohne Position und Konflikte melden
6. **Berechnen:** Menge je Position = Summe der Bauteile, Kosten = Menge × Einheitspreis
7. **Exportieren:** Excel (Kostenschätzung, Bauteilliste, Auffälligkeiten) und IFC-Gesamtmodell

## Installation

Benötigt wird Python 3.10 oder neuer (getestet unter Windows mit PowerShell).

```powershell
python -m venv myenv
myenv\Scripts\activate
pip install -r requirements.txt
```

## Bedienung

### Weboberfläche

```powershell
myenv\Scripts\activate
streamlit run main.py
```

Der Browser öffnet sich unter `http://localhost:8501`. Dort lädst du zuerst die IFC-Dateien hoch,
dann die eBKP-T-Liste. Die Seite führt Schritt für Schritt durch Prüfung, Zuordnung und Kosten.
Am Ende stehen die Downloads bereit. Beenden mit **Ctrl+C** im Terminal.

### Ohne Weboberfläche (Terminal)

```powershell
python pipeline.py                                    # IFC-Dateien und Liste aus dem Ordner daten/
python pipeline.py <ifc-ordner> <liste.xlsx> <ziel.xlsx>
python -m export.ifc_writer ALLE                      # IFC-Gesamtmodell nach daten/ausgabe/
```

Die Pipeline hält an, sobald eine Prüfung einen Fehler meldet.

## Eingabedaten

### IFC-Modelle

- IFC 4.3 (getestet mit Civil 3D 2026), ein oder mehrere Fachmodelle.
- Bezeichnungen und Mengen kommen bevorzugt aus den Property-Sets `GoBau_Struktur` und `GoBau_Menge`.
  Welche Property-Sets gelten, steht im Blatt «Einstellungen» der Liste.
- **Ohne GoBau** funktioniert es auch. Fehlende Bezeichnungen werden aus der IFC-Hierarchie
  ergänzt (IfcRoadPart, IfcElementAssembly, Bauteilname). Fehlende Mengen werden aus der Geometrie
  berechnet und als Hinweis markiert. Siehe «Grenzen».

### eBKP-T-Liste (Excel)

Die Liste hat drei Blätter, die das Programm liest. In allen Blättern stehen die Spaltenköpfe in Zeile 4.

| Blatt | Inhalt |
|---|---|
| Positionen | Pos-ID, eBKP-T Code, Gruppe, Bezeichnung, Mengenart (Stück/Länge/Fläche/Volumen), Einheit, Einheitspreis |
| Zuordnung | Regeln: Pos-ID, IFC-Klasse, Bereich, Bauteilgruppe, Typ/Schicht, Element, Vergleich («gleich»/«enthält») |
| Einstellungen | Welches Property-Set und welcher Property-Name für jedes Feld und jede Mengenart gilt |

Eine Regel passt, wenn **alle ausgefüllten** Filter passen. Leere Filter gelten als «egal».
Jedes Bauteil muss genau eine Position treffen, sonst gibt es einen Konflikt.

> **Wichtig – Lizenz:** Die eBKP-T-Codes und -Bezeichnungen gehören der CRB und sind lizenzpflichtig.
> Dieses Repository enthält keine CRB-Inhalte. Jede Nutzerin und jeder Nutzer verwendet die
> **eigene lizenzierte eBKP-T-Liste**. Die Testvorlage hat leere Codes.

## Ergebnisse

- **Excel-Kostenschätzung** mit den Blättern Zusammenfassung (Total exkl. MwSt., Quelldateien, Datum),
  Kosten je Position, Bauteilliste (GUID, Pos-ID, Menge, Mengenquelle, Kosten) und Auffälligkeiten
- **Diagramm** der Kosten je Gruppe in der Weboberfläche
- **IFC-Gesamtmodell**: alle Fachmodelle unter einem IfcProject, die GUIDs bleiben unverändert.
  Jedes Bauteil trägt das Property-Set `Pset_KOSTRA` (Status, Pos-ID, Menge, Einheitspreis, Kosten, Herkunft).
  Ist in der Liste ein eBKP-T-Code eingetragen, wird er als IfcClassificationReference zugewiesen.
  Die Originalmodelle werden nie verändert.

## Projektstruktur

```
main.py                       Weboberfläche (Streamlit), nur Anzeige und Aufrufe
pipeline.py                   Ganzer Ablauf im Terminal
importers/ifc_reader.py       Bauteile, GUIDs, Hierarchie, Property-Sets, Mengen lesen
importers/sources.py          Ersatzquellen aus der IFC-Hierarchie (ohne GoBau)
importers/geometry.py         Mengen aus der Geometrie (3. Mengenquelle)
importers/ebkp_reader.py      eBKP-T-Liste lesen
validation/model_checks.py    Modell prüfen
validation/list_checks.py     Liste prüfen
calculation/mapping.py        Regeln anwenden, Lücken und Konflikte
calculation/costs.py          Mengen und Kosten je Position
export/excel_writer.py        Excel-Kostenschätzung und Auffälligkeiten
export/ifc_writer.py          IFC-Gesamtmodell mit Pset_KOSTRA
visualization/charts.py       Diagramm Kosten je Gruppe
tests/test_sollwerte.py       Vergleich mit den Sollwerten
daten/                        IFC-Modelle und Liste (nur lokal, nicht im Repository)
```

## Tests

```powershell
python -m pytest tests -v
```

Die Tests vergleichen Anzahl Bauteile, Menge und Kosten je Pos-ID mit dem Blatt «Kontrolle» der
Testvorlage. Sollwerte für das Beispielprojekt (9 Fachmodelle, 852 Bauteile): alle Bauteile genau einer
Position zugeordnet, 0 Konflikte, Total CHF 896'542 exkl. MwSt. Die Toleranz beträgt ±0.01 bei der Menge
und ±1 CHF bei den Kosten, weil das Kontrollblatt mit gerundeten Mengen rechnet. Fehlen die Daten
in `daten/`, werden die Tests übersprungen.

Zusätzlich hat jedes Modul einen Selbsttest, der mit `python -m <modul>` läuft, z.B.
`python -m calculation.mapping`.

## Grenzen

- **Mengen aus der Geometrie sind Näherungen.** Im Vergleich mit GoBau stimmt das Volumen zu 100 %.
  Die Grundrissfläche stimmt bei Schichten und Erdbau zu 90–96 %, die Länge (Hauptachse) bei
  80–85 % der Bauteile auf 2 % genau. Bei senkrechten Bauteilen wie Wänden ist die Fläche falsch,
  weil die Grundrissfläche statt der Ansichtsfläche verwendet wird.
- Die Geometrie-Berechnung ist langsam: Für 852 Bauteile ohne GoBau-Mengen dauert sie etwa 14 Minuten.
- Ein Bauteil im Konflikt erhält keine Pos-ID. Die beteiligten Regeln werden gemeldet und müssen
  in der Liste korrigiert werden.
