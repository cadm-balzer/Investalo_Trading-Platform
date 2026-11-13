# Festes eigenes Basketbudget ohne zusätzlichen Fundingquotenhalt

IP-082, Q45 vom 2026-11-13. Nutzer: „Die Buckets bekommen ja ein festes
reservierts Budget was zur Verfügung steht entsprechend darf es keinen
Blocker geben.“ PR50 ist gemerged; Commit6dfde31 ist Vorfahr von
main bde1cee, über GitHub und Fetch geprüft.

Umsetzung dieses Auftrags: separate `CapitalReservedCashPlan`,
`isolated-usdt-capital-reserved-cash/4`. Das feste Gesamtbudget und alle sechs
Eigenkapitalbeträge bleiben unverändert. Funding wird bei jedem Settlement
tatsächlich aus der eigenen isolierten Margin bezahlt oder dort gutgeschrieben.
Es erzeugt keinen zusätzlichen Anspruch auf noch ungenutztes Nachkaufkapital
und keinen globalen Halt allein wegen Überschreiten der kleinen Kostenquote.

Die Barreserve deckt tatsächlich aus der Wallet gezahlte Ein-/Ausstiegsgebühren
und bereits gezahlte Marginrestoration. Diese Zahlungen bleiben begrenzt.
Die bisherigen Policys1–3 zählen einen ungedeckten negativen Fundingsaldo
zusätzlich gegen die Kostenreserve und bleiben als historische Vergleiche
unverändert.

Restoration verwendet nur eigene verbleibende Kostenreserve. Vorher werden
Gebühren für die noch fehlenden regulären Käufe und einen vollständigen
Ausstieg zurückgehalten. Die Ausstiegsgröße ist das Maximum aus dem Nominal
aller fünf regulären Stufen und aktuellem Marknominal plus noch geplantem
regulärem Nominal, jeweils mit dem eingefrorenen Baskethebel. Der aktuelle
Preis ist eine deklarierte Planung; unbegrenzt steigende spätere Kurse sind
keine garantierte Gebührenquote. Nur das Geldquantum wird abgerundet.
Manuelle sechste Stufe, ungenutzte reguläre Stufen und fremde Reserven werden
nicht zum automatischen Ausgleich von Funding verwendet.

Damit verschwindet der zusätzliche globale Fundingquotenhalt. Das reservierte
Geld erzeugt jedoch keine neue Futuresmargin: nach aufgebrauchter zulässiger
Restoration kann der isolierte Saldo die deklarierte Initialmargin eines
Nachkaufs unterschreiten. Diese Ablehnung bleibt sichtbar, ebenso echte
Liquidation oder tatsächlicher Geldmangel. Das Profil verspricht keine
unbegrenzte Finanzierung der Haltedauer oder stets fünf ausgeführte Käufe.
Diese Grenzen entsprechen Q42 und der unveränderten Eigenkapitalzuordnung.

Alle Gebühren und Funding bleiben vollständig im Nettogewinn. Restoration
ist eine interne Geldbewegung; weder Verlust noch Gewinn wird doppelt
gebucht. Q44 bleibt für vollständig profitable normale Abschlüsse desselben
Zyklus erhalten. Bereits gesetzte Halts werden nicht gelöscht.

Vor Ergebnissen eingefroren: [Protokoll](research-protocols/futures-capital-h1-reserved-cash-20261113.json).
Erster Vergleich: unveränderte fünf native Coins, 10000 USDT, feste2×,
H1-RSI/H1-Supertrend, 2022-08-01 bis 2025-08-01 exklusiv.
Keine Reinvestition, neuen Quellen oder Holdoutdaten. Das neue Planmerkmal
bindet Profil und vollständigen Journalrestore. Public-/Paperprofil, AI,
Broker, Abhängigkeiten und Datenbanken erhalten keine Änderung.

183 unterschiedliche gezielte gepinnte Fälle/108 Subtests bestehen,
neun neue Fälle. Ein anfänglich zu niedriger synthetischer Fundingbetrag
wurde im Markttest erhöht, damit er den alten Halt tatsächlich nachweist;
die zwei betroffenen Markttests wurden gezielt wiederholt. Keine
Wiederholung unveränderter Credential-/DB-/UI-Tests. Eigenreview prüft
alte Cash-/Abschluss-/Signalidentitäten, Full-Genesis-Journal und Quellenbindung.

Expliziter create-only Offlinejob:

```sh
python3 infra/scripts/backtest-futures-capital.py --h1-reserved-cash NEW_OUTPUT_DIRECTORY
```

Der native Lauf und vollständige Restore sind abgeschlossen:
109440 Commands, vier Artefakte erneut gehasht und acht Implementationshashes
gegen Startmanifest/Endstand geprüft. Netto9579,93 USDT, DD17,62%,
269 Abschlüsse, 24 volle Fünfstufen-Baskets, keine Liquidationen/Kontohaltes.
Letzter echter Einstieg2025-07-29; die zwei offenen Endpositionen bleiben
zum Markkurs in der Nettozahl. 29 deklarierte Margin- und32 Preisgrenzen-
ablehnungen bleiben sichtbar; keine zusätzliche Budget-/Cashsperre.
[Ergebnisse und eingefrorener Receipt](futures-reserved-budget-results-20261113.md).
