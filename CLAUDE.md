# Projekt: Kostenschätzung Strassenbau aus IFC und Excel

Semesterprojekt im Modul Digital Twin Programmieren (HSLU, Digital Construction, HS26).
Eine Web-Anwendung in Python (Streamlit) liest ein Strassen-IFC und eine Excel-Preisliste ein,
prüft die Daten, lässt fehlende Angaben über Excel ergänzen und berechnet eine Kostenschätzung
(Menge × Einheitspreis). Das Ergebnis wird als Excel exportiert.

## Wie du (Claude) mit mir arbeitest

- Ich lerne Python noch. Erkläre neuen Code kurz und verständlich, auf Deutsch.
- Arbeite in kleinen Schritten: immer nur ein Modul oder eine Funktion pro Auftrag.
- Code-Kommentare, Variablen- und Funktionsnamen auf Deutsch (ohne Umlaute im Code: `laenge`, `flaeche`).
- Fachlogik nie in `main.py`. Die Oberfläche ruft nur Funktionen aus den Modulen auf.
- Teste neuen Code selbst im Terminal mit den Dateien in `daten/`, bevor du sagst, dass er fertig ist.
- Schlage nach jedem abgeschlossenen Schritt eine kurze Commit-Nachricht vor.
- IFC-Dateien in `daten/` nie committen (stehen in `.gitignore`).
- Wenn ein Schritt fertig ist: Abschnitt «Stand» unten aktualisieren.

## Umgebung

- Windows, VS Code, PowerShell
- Python-Umgebung: `myenv` (aktivieren mit `myenv\Scripts\activate`)
- Module: ifcopenshell, pandas, openpyxl, streamlit, matplotlib (in `requirements.txt`)
- Start der Webseite: `streamlit run main.py`

## Projektstruktur (Ziel)

```
main.py                     Weboberfläche (Streamlit), führt durch die 5 Schritte
importers/ifc_reader.py     IFC lesen: Bauteile, GUID, GoBau_Struktur, GoBau_Menge
importers/price_reader.py   Excel-Preisliste lesen
validation/checks.py        Prüfungen (Fehler sperren, Hinweise erlauben Berechnung)
enrichment/template.py      Excel-Ergänzungsvorlage erstellen und wieder einlesen
enrichment/ifc_writer.py    Ergänzte Angaben als Pset_Kosten ins IFC schreiben (später)
calculation/costs.py        Preise zuordnen, Kosten je Bauteil, Position, Total
visualization/charts.py     Diagramm der Kostenanteile
export/excel_writer.py      Kostenschätzung als Excel schreiben
daten/                      Test-IFC und Test-Preisliste (nur lokal)
```

## Die IFC-Daten (bereits analysiert)

- Projekt «25.011 Sanierung Gimenenstrasse», IFC4X3_ADD2, aus Civil 3D exportiert.
- 9 Fachmodelle: TRAS (Trassee), ENTW (Entwässerung), KUBA (Kunstbauten/Stützkonstruktion),
  PFMO (Pflanzen/Möblierung), AUSS (Ausstattung), SIMA (Signalisation/Markierung),
  WKLN-EW / -SW / -WV (Werkleitungen Elektro, Schmutzwasser, Wasserversorgung). Total ca. 850 Bauteile.
- Klassen u.a.: IfcCourse, IfcKerb, IfcEarthworksFill, IfcPipeSegment, IfcBuiltElement,
  IfcDistributionChamberElement, IfcPipeFitting, IfcValve, IfcFooting, IfcSign.
- Es gibt **keine** IfcElementQuantity. Die Mengen stehen in eigenen Property Sets:
  - `GoBau_Struktur`: `Stufe_1` bis `Stufe_7` (nicht immer alle vorhanden)
    - Stufe_1 Projekt, Stufe_2 «03 Neu», Stufe_3 «Gimenenstrasse»
    - Stufe_4 Bereich (Strassenabschnitt, Buswendeschleife, Privatparzellen, Stützkonstruktion)
    - Stufe_5 Gewerk (z.B. Fahrbahn Oberbau 1, Randabschlüsse, Strassenentwässerung)
    - Stufe_6 Bauteil/Material (z.B. «AC 8 N, d=30mm») → **Hauptschlüssel für die Preiszuordnung**
    - Stufe_7 Detail (z.B. Schachtabdeckung)
  - `GoBau_Menge`: `Anzahl (Stk.)`, `Länge (m)`, `Fläche (m2)`, `Volumen (m3)` (Zahlen)
- Viele Bauteile haben gleichzeitig Länge, Fläche und Volumen. Welche Menge zählt,
  bestimmt die **Einheit der Preisposition** (Stk / m / m2 / m3).
- IfcAnnotation und Elemente ohne `GoBau_Menge` werden ignoriert.

## Fachliche Regeln

- Kosten = Menge (passend zur Einheit) × Einheitspreis, Summen je Position und Total (exkl. MwSt.).
- Bauteile ohne Preis oder ohne Menge werden sichtbar ausgewiesen, nie still mit 0 gerechnet.
- Jede Ergebniszeile ist über die GlobalId auf das Bauteil zurückführbar.
- Das Original-IFC wird nie überschrieben.

## Termine

- 26.10.2026 Zwischenpräsentation 1 (Konzept, Umgebung, Herausforderungen)
- 14.12.2026 Zwischenpräsentation 2 (lauffähiger Prototyp)
- Januar 2027 MEP: Abgabe über GitHub mit README und Dokumentation

## Stand

- [x] Git-Repo, `.gitignore`, `myenv`
- [x] IFC-Struktur analysiert
- [x] `importers/ifc_reader.py` (`lese_ifc`, `lese_alle_ifc`; getestet mit 9 Dateien, 852 Bauteile)
- [ ] Excel-Preisliste festlegen und `price_reader.py`
- [ ] `checks.py`
- [ ] `costs.py`
- [ ] `excel_writer.py`
- [ ] `main.py` (Streamlit)
- [ ] Ergänzung über Excel
- [ ] Diagramm
- [ ] README
