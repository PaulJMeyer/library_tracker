# Library Tracker

## Ziel

Dieses Projekt dient dazu, die persönliche Merkliste der Stadtbibliothek Bremen automatisiert auszuwerten.

Der Fokus liegt auf der passiven Analyse des eigenen Benutzerkontos. Das Programm soll dem Nutzer anzeigen,

* welche Werke aktuell in der Zentralbibliothek verfügbar sind,
* welche Werke kostenlos aus anderen Zweigstellen bestellt werden können,
* welche Werke vollständig ausgeliehen sind,
* welche Medien bereits bestellt wurden.

Das Projekt ist ausschließlich für den privaten Gebrauch vorgesehen.

---

## Aktueller Funktionsumfang

* Login in den Online-Katalog
* Session-Handling inklusive Cookies und CSId
* Auslesen der persönlichen Merkliste
* Unterstützung beliebig vieler Merklisten-Seiten
* Aufruf der Detailseiten aller Werke
* Erkennung mehrerer Exemplare eines Werkes
* Unterscheidung zwischen Zentralbibliothek und Zweigstellen
* Erkennung der Zustände:

  * ausleihbar (verfügbar in der Zentralbibliothek)
  * bestellbar (kostenlos aus einer Zweigstelle)
  * entliehen
  * bestellt
* Extraktion des Rückgabedatums aus dem Status-Text (wird aktuell noch nicht in der Ausgabe angezeigt)
* Sortierte Ausgabe der Ergebnisse nach diesem Schema

---

## Geplante Erweiterungen

### Priorität hoch

* Anzeige von Rückgabedaten in der Ausgabe (Extraktion ist bereits implementiert)
* Übersicht über ausgeliehene Medien
* Erkennung verlängerbarer Medien
* Übersicht über bereits bestellte Medien

### Priorität mittel

* Manuelle Auslösung kostenloser Bestellungen
* Konsolenmenü
* Weitere Funktionen wie:
    - filtern der Neuerscheinungen nach Lieblingsautoren
    - filtern von Büchern nach Genres
    - Abfragen von zwei Account gleichzeitig

### Nicht geplant

* Automatische kostenpflichtige Vormerkungen
* Massenhafte Requests
* Öffentliche Bereitstellung als Dienst
