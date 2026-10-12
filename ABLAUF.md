# Arbeitsablauf: Programmieren mit Claude in VS Code

Alles passiert in VS Code: links deine Dateien, rechts das Claude-Panel, unten das Terminal.
Claude liest beim Start automatisch die Datei `CLAUDE.md` und kennt damit dein Projekt,
deine IFC-Daten und deine Regeln. Du musst nichts mehr von woanders hineinkopieren.

---

## Einmalig einrichten

1. `CLAUDE.md` und `ABLAUF.md` in den Projektordner `HSLU_PROGR_H26` legen.
2. Im Terminal:
   ```powershell
   myenv\Scripts\activate
   pip install ifcopenshell pandas openpyxl streamlit matplotlib
   pip freeze > requirements.txt
   ```
3. Die Ordner anlegen lassen. Prompt ans Claude-Panel:
   > Lies CLAUDE.md. Lege die Ordnerstruktur aus «Projektstruktur» an (mit leeren `__init__.py`)
   > und verschiebe `ifc_reader.py` nach `importers/`. Führe noch nichts anderes aus.
4. Speichern auf GitHub:
   ```powershell
   git add .
   git commit -m "Projektstruktur und CLAUDE.md"
   git push
   ```

---

## Der Arbeitszyklus (für jeden Schritt gleich)

| # | Was du tust | Wo |
|---|-------------|----|
| 1 | **Auftrag geben:** einen Schritt aus dem Plan unten ins Claude-Panel kopieren | Claude-Panel |
| 2 | **Verstehen:** Erklärung lesen. Unklar? Nachfragen: «Erklär mir Zeile X» | Claude-Panel |
| 3 | **Testen:** Datei selbst ausführen (`python -m importers.ifc_reader` o.ä.) | Terminal |
| 4 | **Fehler?** Fehlermeldung ins Claude-Panel kopieren: «Das kommt beim Ausführen: …» | Claude-Panel |
| 5 | **Sichern:** `git add .` → `git commit -m "…"` → `git push` | Terminal |
| 6 | **Stand nachführen:** «Aktualisiere den Stand in CLAUDE.md» | Claude-Panel |

Faustregeln:
- Ein Auftrag = ein Modul. Nie «Bau mir das ganze Programm».
- Nach jedem funktionierenden Schritt committen. So kannst du immer zurück.
- Code, den du nicht erklären kannst, ist an der Präsentation ein Risiko. Frag nach, bis es klar ist.
- Neuer Arbeitstag: im Panel einfach starten mit «Lies CLAUDE.md, was ist der nächste Schritt?»

---

## Der Plan Schritt für Schritt (mit Prompts)

### Phase 1 – bis Zwischenpräsentation 1 (26.10.)

**Schritt 1: IFC einlesen testen**
> Teste `importers/ifc_reader.py` mit allen Dateien in `daten/`. Zeig mir die Anzahl Bauteile
> pro Datei und die Mengen pro Stufe_4/Stufe_5. Erklär mir die Funktion `lese_ifc` Zeile für Zeile.

**Schritt 2: Liste aller Bauteiltypen für die Preisliste**
> Erstelle mir aus allen IFC-Dateien eine Excel-Liste aller verschiedenen Stufe_6-Werte mit
> Stufe_5, Anzahl Bauteile und Summe von Länge, Fläche, Volumen. Daraus baue ich meine Preisliste.

→ Diese Liste in Excel öffnen und daraus deine **Preisliste** machen:
Spalten `Position`, `Bezeichnung` (= Stufe_6), `Einheit` (Stk/m/m2/m3), `Einheitspreis_CHF`.
Als `daten/preisliste.xlsx` speichern.

**Schritt 3: Material für die Präsentation**
> Fasse für meine Zwischenpräsentation 1 zusammen: welche IFC-Klassen, Property Sets und Mengen
> vorhanden sind und was das für die Umsetzung bedeutet. Kurz, in Stichworten.

### Phase 2 – Kernfunktionen (02.11.–23.11.)

**Schritt 4: Preisliste einlesen**
> Schreibe `importers/price_reader.py`: liest `daten/preisliste.xlsx` mit pandas, prüft die
> Pflichtspalten und gibt einen DataFrame zurück. Teste es.

**Schritt 5: Prüfungen**
> Schreibe `validation/checks.py` gemäss den Regeln in CLAUDE.md: fehlende Mengen, doppelte
> Positionen, leere Preise, Bauteile ohne passenden Preis, Einheit ohne passende Menge.
> Unterscheide Fehler (sperren) und Hinweise. Gib die Ergebnisse als Tabelle zurück.

**Schritt 6: Kosten berechnen**
> Schreibe `calculation/costs.py`: verknüpft Bauteile über Stufe_6 mit der Preisliste, wählt die
> Menge passend zur Einheit, rechnet Kosten je Bauteil, je Position und Total.
> Bauteile ohne Preis separat ausweisen.

**Schritt 7: Excel-Export**
> Schreibe `export/excel_writer.py`: Excel mit den Blättern Zusammenfassung, Kosten je Position,
> Bauteilliste (mit GlobalId) und Auffälligkeiten.

**Schritt 8: Alles in einem Testlauf**
> Schreibe ein kurzes Skript, das Schritte 1, 4, 5, 6, 7 nacheinander mit den Dateien in
> `daten/` ausführt, damit ich den ganzen Ablauf ohne Webseite testen kann.

### Phase 3 – Webseite bis Zwischenpräsentation 2 (14.12.)

**Schritt 9: Streamlit-Grundgerüst**
> Schreibe `main.py` mit Streamlit: Upload für IFC (mehrere Dateien) und Preisliste,
> danach Prüfergebnisse und Kostentabelle anzeigen, Download-Button für das Excel.
> Nur Funktionen aus den Modulen aufrufen. Erklär mir, wie Streamlit funktioniert.

Starten mit `streamlit run main.py`, im Browser testen.

**Schritt 10: Ergänzung über Excel**
> Schreibe `enrichment/template.py`: Vorlage mit allen Bauteilen ohne Preiszuordnung
> (GlobalId, Stufe_6, leere Spalte Preisposition) und Funktion zum Wiedereinlesen.
> Baue es als Schritt in `main.py` ein.

**Schritt 11: Diagramm**
> Schreibe `visualization/charts.py`: Balkendiagramm der Kosten je Stufe_5 mit Matplotlib,
> und zeig es in `main.py` an.

### Phase 4 – Abschluss bis MEP (Januar)

**Schritt 12: IFC zurückschreiben**
> Schreibe `enrichment/ifc_writer.py`: schreibt Preisposition, Einheitspreis und Kosten als
> `Pset_Kosten` in eine Kopie des IFC. Das Original bleibt unverändert.

**Schritt 13: Aufräumen und README**
> Prüfe das ganze Projekt: unnötiger Code, fehlende Kommentare, Fehlerbehandlung.
> Schreibe dann eine README.md mit Zweck, Installation, Bedienung und Projektstruktur.

---

## Wenn etwas nicht klappt

- **Fehlermeldung:** komplett ins Panel kopieren, nicht nur die letzte Zeile.
- **Claude hat zu viel geändert:** `git diff` zeigt die Änderungen, `git checkout -- datei.py` setzt eine Datei zurück.
- **Claude vergisst den Kontext:** «Lies CLAUDE.md nochmals» schreiben.
- **`git push` wird abgelehnt:** zuerst `git pull`, dann nochmals `git push`.
