# Brokerintegrationen

Bitget: BTC/USDT und ETH/USDT Spot ohne Hebel auf H4 sind bestätigt.
Nutzerkonto ist Classic mit getrennten Spot-/Futures-Wallets; private
Classic-V2-Anbindung zuerst. Jeder Plattformnutzer erstellt eigenen API-Key,
Secret und Passphrase im eigenen Konto. UID-/Parent-/Rechteprüfung,
geschützte Eingabe und separate Budgets: [Bitgetplan](../docs/bitget-connection.md).
Der isolierte [Classic-V2-Readadapter](bitget/README.md) ist implementiert und
mit 24 Offline-Tests geprüft. Nur Kontoinfo und getrennte Walletabfragen;
Vault, Cockpiteingabe und tatsächliche Kontoverbindung folgen.

MT5: bestehende EAs als Referenz; authentifizierte nutzereigene Terminalbridge
mit lokalem Journal und Abgleich. Keine laufenden Referenzsysteme ändern.
Startstrategie ist XAUUSD Trend/Pullback H1/M15 nach unabhängiger Validierung.
MT5 läuft laut Nutzer auf einem separaten Heimnetzserver. Neue Bridge ausgehend
über authentifiziertes HTTPS zum zentralen Einstieg, ohne eingehende Routerports.
Getrenntes Brokerdemo und feste Konto-/Gerätebindung: [MT5plan](../docs/mt5-bridge.md).

Markt-, News- und Makrodaten benötigen geprüfte Nutzungsrechte und Quoten.
Details: [Architektur](../docs/architecture.md), [Trading](../docs/trading.md),
[Quellen](../docs/sources.md).
