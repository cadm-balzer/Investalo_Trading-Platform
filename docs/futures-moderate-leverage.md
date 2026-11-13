# Feste 3×-/4×-Baskethebel und manuelle Liquidationsfreigabe

IP-087 ergänzt auf Nutzerwunsch die bestehenden2×/5×/10× um3× und4×.
PR55 ist am2026-11-13 noch offen; der Branch baut auf dessen unverändertem
Ergebnischeckpoint4ad9a4e auf.

Das [vorab eingefrorene Protokoll](research-protocols/futures-capital-grid-moderate-leverage-20261113.json)
hat SHA256 `79308ab0b727f848ec1c446b096a1c501392ab8592ae6d67fbbc39a0669b760e`.
Nur3×/4× werden neu gerechnet; alle zwölf Originalartefakte und die
vollständig restaurierten Receipts von2×/5×/10× werden vor und nach dem
Lauf überprüft. Unveränderte Daten, H1-RSI/H1-Supertrend, fünf Slots,
10000 USDT, eigene sechs Kapitalstufen, Raster, Kosten, Funding und
Margin-/Liquidations-/Preisregeln. Der Hebel gilt für den ganzen Basket.
Liquidation bleibt terminal; keine hypothetische manuelle Wiederbelebung
oder automatisch simulierte sechste Stufe.

`ModerateEconomicScenario` besitzt eine separate Protokollidentität.
Die alte Szenario-Whitelist und alte2×-/5×-/10×-Digests bleiben erhalten.
Nur explizite vollständige Auswahl des neuen H1-Rasterprofils erlaubt3×/4×.
Jeder Lauf restauriert sein ganzes Journal; elf Implementationsdateien
bleiben zwischen Start und Restore eingefroren.

```bash
bash infra/scripts/check-paper-storage.sh -k 'ModerateGridLeverageTests or GridLeverageResearchTests or CurrentGridResearchTests or EconomicProfileTests'
python3 infra/scripts/backtest-futures-capital.py --h1-grid-moderate-leverage NEW_OUTPUT_DIRECTORY
```

Ergebnisse erst nach vollständigem Restore, Hashabgleich und Erfolgsreceipt.
Derselbe Forschungszeitraum ist kein unabhängiger Holdout. Die spätere
kausale AI-Regimebewertung wird durch fixe Hebel nicht bewiesen.
Aktuelle2026-Bitget-Raster auf2022–2025-Binance-Daten bleiben eine deklarierte
Modellachse, ohne historische Brokerzulassungsbehauptung.

## Nutzerauftrag zur manuellen Wiederbelebung

Q46 bestätigt einen manuellen Schritt nach Liquidation: Startseitenhinweis
mit betroffenen Assets, Details zu Zeitpunkt, Zyklus, Verlust und Sperrgrund
sowie „Wiederbeleben“. Der Verlust bleibt gebucht. Ein neuer Basket benötigt
einen frischen Einstieg und eine neue vorab eingefrorene Hebelentscheidung.
Eine Freigabe setzt keine unmittelbare Kauforder ab.

Vor Freigabe müssen aktuelle eigene Position, offene/ungeklärte Aufträge,
abgeschlossene Liquidationsbuchung und vollständige neue Kapitaldeckung
feststehen. Unverbrauchtes Stufenkapital allein ist nach einem Verlust kein
vollständiges neues Basketbudget. Sperren anderer Assets und Kontohalts bleiben.
Historische Backtest-Liquidationen dürfen nicht als aktuelle Kontosperren
angezeigt oder rückwirkend aus Ergebnissen entfernt werden.

Die aktuelle Runtime betreibt Spot-Paper; native Futures sind bislang lokale
Forschungsjobs. Eine produktive Futures-Reconciliation und dauerhafte
Aktionsanbindung sind daher ein eigener Implementationsschritt IP-088.
Keine Aktivierung von Echtgeldhandel oder AI durch diesen Forschungsauftrag.
