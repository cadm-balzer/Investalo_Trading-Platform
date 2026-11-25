# Operativer automatischer H1-Demohandel

25.11.2026: PR129/main`6016037` verifiziert. Der Nutzer beauftragt die
vollständige Worker-/Strategieanbindung und hat automatischen Demohandel,
Originalstart1 und die [Demo-Ausnahme](bitget-demo-worker-authorization.md)
bereits ausdrücklich freigegeben.

## Tatsächlicher Betriebsstand

**Demohandel aktiv**, native Workerbeobachtung25.11.2026 15:56:09.873UTC:
`running / waiting_for_h1_signal / execution_enabled=true`, Journalrevision13.
Alle300 ursprünglichen H1-Stunden für RSI/Supertrend sind verarbeitet.
Originaler Start1 wählt AVAX,BNB,BTC,ETH,LINK,SOL,XRP mit Obergrenze3.
Native Profile wurden vorbereitet: isoliert, einseitig,2×.
Zwölf einmalige Konfigurationsversuche wurden durch anschließende native
GETs bestätigt; ein vorübergehender lesender Transportfehler wurde überwunden.

Tatsächlicher Worker-Neustart danach:15:57:15.685UTC wieder `running`,
Journal und externer Receipt byteidentisch, weiterhin Revision13.
Bis zu diesem Prüfstand keine Strategieorder; der Worker wartet auf ein
frisches abgeschlossenes H1-Signal. Ein aktiver Worker erzeugt keine
erzwungenen Einstiege ohne RSI-/Kapitalbedingungen.

Cockpit healthy/TLS200, anonyme Control GET+POST401. Neuer Dienst ohne
Hostport, UID10003, readonly Rootfs, Logging deaktiviert; sechs andere
bestehende Dienste/Images unverändert. Originale Keymetadaten active1/1,
private Hashes und technisches BTC-Testjournal8 erhalten.
Private Rollout-/Image-/Hashbelege: `infra/local/demo-h1-worker/rollout-*`.

Auf weiteren Deployments **acht Overlays** erhalten: Public/Paper/Demo-
Trading/Admin-Mail/Account-Sync/Market-Test/H1-Control/**H1-Worker**.
Der mutable Executortag wurde gebaut, der bestehende Credential-Executor
wurde nicht erneuert. Der Worker verwendet das geprüfte neue Image.

## Strategie und Kapital

Eigener nativer Plan mit tatsächlichem Startkapital, bestätigtem Mengen-/
Preisraster und explizit unbekannter Market-Höchstmenge. Ohne konto- und
keygebundene genehmigte Policy bleibt diese Angabe gesperrt; keine lokale
Grenze wird als Brokermaximum behauptet.

Fünf automatische Käufe und sechste manuelle Reserve; Stufenbeträge bleiben
Eigenkapital-Margin, Menge=floor(Stufenmargin×2/Planungspreis).
RSI14/Wilder auf geschlossenen H1-Kerzen: zwei unter30 für den ersten Kauf,
Rearm über30 und mindestens5% unter dem letzten tatsächlichen Stufenfill
für Nachkäufe. +5% zum tatsächlichen Durchschnitt aktiviert H1-Supertrend/
Netto-Breakeven-Protektion; ursprünglicher Notausstieg bleibt im gemeinsamen
Kernel. Marketfills können vom Planungskurs abweichen.

Verbindliche Budgets, tatsächliche Gebühren/Funding und native Margin-
zuordnung bleiben im bestehenden Ledger. 6%/8%-Kontoverlustgrenzen sind
Warnungen, keine Kaufstaffelblocker. Native Marker, Orderevidenz und
Positionsabgleich erzeugen die Buchung; keine Paperfills oder ACK-Fillannahme.
Öffentliche Gebühren dienen nur der Planung; tatsächliche Kosten werden
nativ gebucht. Die Maintenanceannahme des Planungsmodells bleibt ausdrücklich
deklariert, keine behauptete native Tierbestätigung.

Basketobergrenzen können aktualisiert werden, ohne vorhandene Kapitalstaffeln
umzuschreiben. Drei profitable Abschlüsse und eine vollständig gedeckte neue
Range erlauben weitere Slots bis7; danach größere zukünftige Volumina.
Offene Baskets behalten ihr Budget. Die bestehende Profitlogik wird auf echte
native Abschlussdaten angewendet.

## Laufzeit und Schutzgrenzen

Eigener privater Worker liest die **aktuelle** originale signierte Control-
Datei, keinen Snapshot und keine Browsersitzung. Separate Gruppen geben nur
Lesezugriff auf den Control-Unterordner; kein Mount aller Cockpit-Sessions.
Nur der abgeleitete Intentkey, originaler Trading-AEAD-Pfad und020 werden
verwendet. Actor/Epoch/reauth/Konto/Key bleiben aktuell geprüft.

Genuine aktuelle Kontoquelle zuerst nach dem historischen Datenabruf; Warmup
verändert keine historischen Gelder oder Fills. Laufende native H1-Kerzen
aktualisieren Indikatoren unabhängig von bereits erfolgten Finanzbeobachtungen.
Versäumte Stunden erzeugen keine rückwirkenden Orders. Eine frische native
Bewertung bildet den tatsächlich beobachteten Tagesbeginn nach Ausfällen,
keinen erfundenen Mitternachtssaldo; historische Schemas bleiben strikt.

Vor jeder Order: aktuelles Zielprofil, volle eigene Positionen, aktueller
Cashabgleich, alle fünf Pendingfamilien sowie unabhängige native Identität.
Dauerhafter Commandverbrauch und unbekannter Versandstand vor POST;
Wiederanlauf beobachtet ausschließlich per GET. Pause sperrt Käufe und lässt
Positionsmanagement und eigene Reduce-only-Abschlüsse laufen.

Konfigurationsänderungen sind ebenfalls einmalig vor POST markiert, nur
auf frisch bestätigtem Flat-Konto mit fünf leeren Pendingfamilien. Eine
unbestätigte Änderung wird per GET geprüft und niemals erneut gesendet.
Fremde/native abweichende Positionen, ungeklärte finanzielle Zuordnung oder
Historylücken sperren neue Orders und bleiben im Workerstatus sichtbar.
Liquidations-/Fremdpositionsabweichungen werden nicht als gewöhnlicher
gewinnbringender Sell erfunden; die native Klärung bleibt erforderlich.

Dashboardstatus stammt aus einer frischen signierten Workerdatei und wird
alle10s bei sichtbarem Tab aktualisiert. Veraltete oder nicht passende
Actor-/Key-/Controlrevisionen zeigen keinen aktiven Handel an.

## Prüfung und Rückkehr

196 relevante gepinnte Pythonfälle,12 Nodefälle, vollständige Typprüfung und
finale Cockpit-/Executorbuilds grün. Darunter vollständiger nativer
Stufeneinstieg/Fee-/Marginabgleich, verlorener POST-ACK ohne Doppelorder,
Pause mit Reduce-only-Abschluss, originaler Restore mit unbekannten Grids,
native Tagesbasis, Kapitalerhalt bei Obergrenzenänderung und historische
Ledger-/Paperregression. Native öffentliche sieben-Asset-Marktquelle geprüft.

Vor dem ersten Versand ist ein Image-/Overlayrollback mit erhaltenem
Journal möglich. Nach tatsächlichen Strategieorders neue Käufe pausieren
und Positionsmanagement mit einem kompatiblen Worker erhalten; keine
Journal-/Consumermarker löschen, keine Rückkehr zu einem Image ohne native
Plan-/Journalunterstützung. Geprüfte Fixes erhalten den gesamten Originalstand.
