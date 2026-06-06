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
* Status erkennen
* Zukünftig:

  * Exemplare
  * Zweigstellen
  * Rückgabedaten
  * Bestellmöglichkeiten

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

Diese Datei wird niemals in Git versioniert.

---

## requirements.txt

Python-Abhängigkeiten des Projekts.
