# AI_CONTEXT

## Projektbeschreibung

Dieses Repository enthält ein privates Python-Projekt zum Auslesen des Benutzerkontos der Stadtbibliothek Bremen.

Der Zweck ist die komfortable Übersicht über die eigene Merkliste und das eigene Bibliothekskonto.

Das Projekt soll Web-Scraping und Session-Handling demonstrieren und dient gleichzeitig als persönliches Alltagswerkzeug.

---

## Wichtige Projektziele

Der Nutzer möchte folgende Endzustände unterscheiden:

1. ausleihbar

   * mindestens ein Exemplar in der Zentralbibliothek verfügbar

2. bestellbar

   * kein Exemplar in der Zentralbibliothek verfügbar
   * aber kostenlos aus einer anderen Zweigstelle bestellbar

3. entliehen

   * alle relevanten Exemplare ausgeliehen

4. bestellt

   * der Nutzer hat bereits eine kostenlose Bestellung ausgelöst

Die Ausgabe soll genau in dieser Reihenfolge sortiert werden.

---

## Harte Randbedingungen

### Niemals automatisch vormerken

Vormerkungen kosten Geld (1 €).

Das Projekt darf niemals automatisch eine Vormerkung auslösen.

Insbesondere dürfen keine Aktionen ausgeführt werden, wenn Begriffe wie

* Vormerkung
* Gebühren
* 1,- Euro

erkannt werden.

---

## Bestellungen

Kostenlose Bestellungen aus anderen Zweigstellen sind grundsätzlich erwünscht.

Eine automatische Bestellung soll jedoch erst in einer späteren Projektphase implementiert werden und ausschließlich nach expliziter Benutzerbestätigung erfolgen.

---

## Coding Style

* einfache, gut lesbare Funktionen
* keine unnötig komplexen Klassenhierarchien
* BeautifulSoup für HTML-Parsing
* requests.Session für HTTP-Kommunikation
* klare Trennung zwischen

  * HTTP
  * Parsing
  * Geschäftslogik
  * Ausgabe

---

## Aktueller Stand

Implementiert:

* Login
* Session-Handling
* Merkliste über mehrere Seiten
* Statuserkennung
* Sortierung

In Arbeit:

* Mehrere Exemplare pro Werk
* Bibliothekszweig-Erkennung

Geplant:

* Kontoübersicht
* Rückgabedaten
* Verlängerungen
* Bestellungen
* weitere Funktionen
