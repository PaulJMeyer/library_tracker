# Projektstruktur

## client.py

Zentrale HTTP-Hilfsfunktionen.

Aufgaben:

* URL-Erzeugung
* GET-Requests
* POST-Requests
* Timeout
* Request-Delays

---

## login.py

Verwaltet den Login-Prozess.

Aufgaben:

* Login-Seite abrufen
* CSId extrahieren
* Login durchführen
* Session zurückgeben

---

## wishlist.py

Verarbeitet die persönliche Merkliste.

Aufgaben:

* Merklistenseiten laden
* Pagination behandeln
* Verfügbarkeitslinks extrahieren

---

## parser.py

Extrahiert Informationen aus den HTML-Seiten.

Aufgaben:

* Titel extrahieren
* Mehrere Exemplare pro Werk erkennen (`parse_copies`)
* Zweigstelle vs. Zentralbibliothek unterscheiden (`is_central`)
* Status pro Exemplar normalisieren (`normalize_copy_status`) und Gesamtstatus ableiten (`classify_item`)
* Rückgabedatum aus dem Status-Text extrahieren (`extract_due_date`) — Wert liegt vor, wird aber noch nicht ausgegeben
* Zukünftig:

  * Rückgabedaten in der Ausgabe anzeigen
  * Bestellmöglichkeiten (automatische Bestellung)

---

## main.py

Einstiegspunkt des Programms.

Aktueller Ablauf:

1. Login
2. Merkliste laden
3. Alle Werke durchlaufen
4. Status bestimmen
5. Sortierte Ausgabe erzeugen

---

## .env

Enthält ausschließlich:

* LIBRARY_USERNAME
* LIBRARY_PASSWORD

---

## requirements.txt

Python-Abhängigkeiten des Projekts.
