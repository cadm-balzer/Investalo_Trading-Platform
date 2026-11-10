# Offlineprofil: gemeinsame Kapital- und Kaufprüfung

Stand2026-11-10, IP-057. IP-056 (`698146f`) ist in Main`3bb0d0c` verifiziert.
Q33 bestätigt3–5 Coinbaskets, volle Kontoplanung und weiterhin6% Tages-/
8% Startkapitalverlust. **2026-11-10 bestätigt der Nutzer gleiche größere
Budgets und die zusätzliche Stressregel für den nächsten Offline-Forschungslauf.**
IP-058 verbindet sie jetzt mit der vollständigen RSI-Nachkaufstaffel.
[Forschungsadapter und Grenzen](staged-portfolio-research.md).

`packages/trading/src/investalo_trading/allocation.py` enthält einen
stdlib-Offlinekern. Bestehende Strategieversion, normale Paper-/Researchcaller,
Snapshots, Datenbanken und Entwicklungsvorschau sind unverändert.
Keine neuen Leistungsergebnisse oder Holdoutabnahme aus den folgenden Zahlen.

## Bestätigtes Forschungsprofil

10.000 USDT werden gleich auf ausgewählte3–5 Coins verteilt. Kostenreserve
mindestens1% **des Principals**, wie bisher500+5. Geldrundung nach unten auf
0,00000001 USDT; Slot-/Stufenreste bleiben getrennt. Kein Hebel.

| Coins | Gesamt je Slot | Principal je Slot | Kosten je Slot | Reguläre erste Stufe | Manuelle sechste Reserve |
|---|---:|---:|---:|---:|---:|
| 3 | 3333,33333333 | 3300,33003300 | 33,00330033 | 293,13365892 | 894,57293374 |
| 4 | 2500 | 2475,24752475 | 24,75247525 | 219,85024419 | 670,92970030 |
| 5 | 2000 | 1980,19801980 | 19,80198020 | 175,88019535 | 536,74376024 |

Sechs Gewichte1,25⁰ bis1,25⁵; nur die ersten fünf sind regulär.
Die letzte Reserve wird durch diese Bibliothek niemals als Kauf ausgelöst.
RSI-/Stufen-/Preisbedingungen, Schutz und manuelle MFA bleiben im bestehenden
Strategie-/Anwendungspfad. Der Allokator beurteilt einen vorgelegten Kandidaten,
ohne dessen RSI-Signal oder manuelle Berechtigung zu bestätigen.
Symbole sind Offlineeingaben, keine Erweiterung der bisherigen BTC-/ETH-Whitelist.

## Kaufprüfung und nachvollziehbare Ablehnung

Equity `E = Cash + Σ(Menge × aktueller Bid)`. Verfügbarer Verlustspielraum:

`H = min(E − 0,94 × Mitternachtsbasis, E − 0,92 × Startkapital)`.

Kontolimits beziehen sich auf diese beiden Basen, nicht auf Peakdrawdown.
Kein Kauf bei erschöpftem Spielraum oder bestehendem Halt. Für den Vorschlag
wird zusätzlich jeder gehaltene Coin bis50% seines ersten tatsächlichen Fills
gestresst:

`S = Σ max(0, Menge × (Bid − 0,5 × erster Fill))`.

Ein bereits unter diesem Stresspreis stehender Coin liefert keinen
rechnerischen Gewinn zum Ausgleich anderer Verluste. Für offene Käufe `P`
und den Kandidaten `K` werden jeweils50% Principal angesetzt.
Weitere Käufe müssen dafür ein tatsächlich durchsetzbares Maximalpreislimit
höchstens zum ersten Fill besitzen. Ein erster Kauf verwendet seinen späteren
eigenen ersten Fill als Referenz. Kein garantierter Preis bei Gaps.
Alle noch nicht bezahlten Slotkosten `C` gehen einmal ein:

`S + 0,5 × P + 0,5 × K + C ≤ H`.

Bezahlte Kosten haben Cash/Equity schon reduziert; sie werden nicht nochmals
abgezogen. Geschätzte Orderfees müssen in ihre verbleibende Slotreserve passen.
Offene Principalbeträge, sämtliche ungenutzten Kostenreserven und der globale
Zuordnungsrest sind außerdem für neue Käufe nicht als Cash verfügbar.
Lifetime-Principal je Slot bleibt nach Teil-/Vollverkauf verbraucht.

Die maximale Principaldiagnose ist nach unten gerundet:

`max(0, min(Slotrest, Cashrest, 2 × (H − S − 0,5 × P − C)))`.

Der vorgelegte Kauf wird vollständig angenommen oder mit Gründen abgelehnt;
keine stillen kleineren Orders oder Änderungen der Stufengrößen.
Bei ungültiger Evidenz/Fees ist der ausgewiesene Maximalbetrag null.

Beispiel mit fünf leeren Slots: `H=600`, `C=99,009901`; dadurch zusammen
höchstens**1001,980198 USDT** neues Kaufprincipal, bevor vorhandene Käufe/
Positionen zählen. Fünf erste reguläre Stufen mit insgesamt879,40097675 USDT
passen in diesen Test. Spätere Stufen können gesperrt werden. Vollständige
Zuordnung von10.000 USDT ist daher weiterhin keine Vollinvestition.
Diese konservative Regel kann die Kapitalnutzung erheblich begrenzen; ihr
Nutzen und entgangene Einstiege gehören in den nächsten Vergleichslauf.

## Evidenz, Reservierung und Integrationsgrenzen

Plan/Anfrage/View binden Tenant, Konto, Policydigest und Revision. Die
Symbolreihenfolge wird kanonisch sortiert und bestimmt keine Signalpriorität.
Ein vollständiger gleichzeitiger Bidstand aller gewählten Assets, positive
UTC-Mitternachtsbasis und höchstens30 Sekunden alte Sicht sind erforderlich.
Keine fehlenden/fremden/duplizierten Assets oder überlappenden offenen Käufe.
Die Mitternachtsbasis muss später aus dem bestätigten Q32-Vertrag stammen;
diese Bibliothek berechnet oder beglaubigt sie nicht.

`reserve_purchase` liefert eine neue immutable Sicht mit Revision+1.
Wiederverwendung einer alten Anfrage wird in dieser neuen Sicht abgelehnt.
Unklarer Orderausgang oder angeforderte Stornierung bleiben reserviert und
sperren weitere Käufe. Die Bibliothek besitzt keinen Fill-, Release-, Retry-
oder Resetpfad; tatsächliche Abwicklung muss später autoritativ abgeglichen
werden. Ausgegebene Budgets werden innerhalb einer Allokation nicht erneuert.
Wiederbelegung nach abgeschlossenem Basket braucht einen eigenen definierten
Allokations-/Zyklusvertrag und kann nicht durch Verkäufe simuliert werden.

Ein Caller muss authentifizierte vollständige Positionen **einschließlich
aller Kontorisiken** und verbleibende offene Orderbeträge/Fees liefern.
Die Bibliothek kann ausgelassene fremde Bestände oder falsche Brokerdaten
nicht erkennen. Bereits bestätigte Teilfills gehören in Cash/Menge/Spent;
nur ungefüllte Restbeträge gehören in Reservierungen.
Revision/Viewdigest sind lokale Diagnose, keine persistente CAS, globale
Einmaligkeit, MFA, ausführbare Freigabe oder Broker-Reconciliation.
Ohne deren Implementierung darf dieser Vorschlag keine Orders versenden.

## Prüfung und nächster Schritt

20 neue synthetische Domainfälle prüfen Kapitalerhaltung, gemeinsame
Reservierungen, genaue Stress-/Cash-/Gebühren-/Budgetgrenzen, verbrauchte
Budgets nach Verkäufen, Preisbindung, Revision/Identität, UTC-/Markfrische,
fehlende Evidenz, unklare Orders und Decimalkontext.
Gezielte gepinnte Regression umfasst außerdem bisherigen Trading-/Paperkern,
joint Quotes, Portfolioreferenz und Workerberechnung; Ergebnis im Taskboard.

Das Budget-/Stressprofil ist für Forschung bestätigt; IP-058 liefert einen
eigenen versionierten Adapter mit Ablehnungsjournal. Vor erweitertem Leistungslauf
noch Coinauswahl/echte Instrumentregeln/Historien, Wiederbelegung und
Signalpriorität festlegen und Inputs einfrieren. Holdout bleibt bis Auswahl geschützt.
Keine implizite Strategie-, öffentliche Deployment- oder Livefreigabe.
[Gesamtplan](multi-basket-ai-plan.md).
