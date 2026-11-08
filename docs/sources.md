# Offizielle Quellen und Best-Practice-Abgleich

Prüfdatum: 2026-11-06. Nur öffentliche Dokumentation recherchiert; keine
Credentials oder privaten Kontodaten an Anbieter übermittelt.
Anbieterregeln/Quoten vor Implementierung und Livefreigabe erneut prüfen.
Die folgenden Compose-/Authelia-/Indikatorergänzungen wurden am 2026-11-07 geprüft.
Transaktionsfreigabe und fatal UTF8 wurden für IP-045 am 2026-11-08 geprüft.

| Thema | Offizielle Quelle | Relevanz |
|---|---|---|
| PostgreSQL RLS | https://www.postgresql.org/docs/current/ddl-rowsecurity.html | Default-deny, Owner-/Superuser-Bypass, `WITH CHECK`, Grenzen |
| Tenantkontext | https://www.postgresql.org/docs/current/sql-set.html | `SET LOCAL` endet mit der Transaktion |
| PITR | https://www.postgresql.org/docs/current/continuous-archiving.html | Basebackup/WAL; `pg_dump` allein nicht ausreichend |
| OAuth | https://www.rfc-editor.org/rfc/rfc9700.html | PKCE, Redirect-/Token-/Refreshschutz |
| MFA | https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html | Phishingresistenz und sichere Recovery |
| Transaktionsfreigabe | https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html | Servergebundene Daten, getrennte Zustimmung, Einmalverbrauch und letzte Prüfung vor Ausführung |
| Fatal UTF8 | https://developer.mozilla.org/en-US/docs/Web/API/TextDecoder/fatal | Defekte Credentialbytes abweisen statt durch Ersatzzeichen verändern |
| Secrets | https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html | Least privilege, Rotation, Audit und Lifecycle |
| AI-Agenten | https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html | Begrenzte Tools und Rechte |
| Prompt Injection | https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html | Externe Inhalte als untrusted Daten |
| Outbox | https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html | Atomare Übergabe; Consumer müssen Duplikate behandeln |
| FastAPI Deployment | https://fastapi.tiangolo.com/deployment/concepts/ | Prozess-/Speicherbedarf, HTTPS, Neustarts |
| Next.js Self-hosting | https://nextjs.org/docs/app/guides/self-hosting | Reverse Proxy, Cache und private Antworten |
| systemd Ressourcen | https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html | cgroup-Limits und Ressourcenpriorität |
| systemd Isolation | https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html | Dienstidentitäten und Prozess-/Dateisystemschutz |
| Docker Ubuntu | https://docs.docker.com/engine/install/ubuntu/ | Ubuntu 26.04 unterstützt; veröffentlichte Ports können UFW umgehen |
| Compose Produktion | https://docs.docker.com/compose/how-tos/production/ | Single-Server-Betrieb möglich, zusätzliche Hardeningkonfiguration nötig |
| Authelia systemd | https://www.authelia.com/integration/deployment/bare-metal/ | Fertiger lokaler OIDC-/MFA-Provider mit systemd-Beispielen |
| Authelia Nutzer | https://www.authelia.com/configuration/first-factor/introduction/ | Keine interne öffentliche Registrierung |
| Authelia Passwort | https://www.authelia.com/configuration/first-factor/file/ | Argon2-Speicherbedarf bei parallelen Logins |
| Authelia OIDC | https://www.authelia.com/configuration/identity-providers/openid-connect/clients/ | Zwei-Faktor-Clientpolicy und PKCE |
| Authelia Sessions | https://www.authelia.com/configuration/session/introduction/ | Memory-/Redis-Sessionoptionen |
| Authelia WebAuthn | https://www.authelia.com/configuration/second-factor/webauthn/ | Alleiniger Passkey nicht pauschal als stabile MFA werten |
| Authelia Docker | https://www.authelia.com/integration/deployment/docker/ | Explizite Nonroot-UID statt nur PUID/PGID |
| Authelia PostgreSQL | https://www.authelia.com/configuration/storage/postgres/ | Eigene IdP-Datenbank und Rolle |
| Authelia Migrationen | https://www.authelia.com/configuration/storage/migrations/ | Automatische eigene Schemamigration beim Start |
| Authelia Notifier | https://www.authelia.com/configuration/notifications/introduction/ | Genau ein Notifier erforderlich |
| Authelia File-Notifier | https://www.authelia.com/configuration/notifications/file/ | Nur Tests; Codes/Links geschützt halten |
| Authelia SMTP | https://www.authelia.com/configuration/notifications/smtp/ | TLS und geeigneter produktiver Mailweg |
| Authelia Elevation | https://www.authelia.com/configuration/identity-validation/elevated-session/ | Zweitfaktorpflicht nicht per Default gegeben |
| Authelia TOTP-Reset | https://www.authelia.com/reference/cli/authelia/authelia_storage_user_totp_delete/ | Kontobezogener administrativer Faktorreset |
| Authelia WebAuthn-Reset | https://www.authelia.com/reference/cli/authelia/authelia_storage_user_webauthn_delete/ | Kontobezogenes Entfernen verlorener Geräte |
| Authelia OIDC-Support | https://www.authelia.com/integration/openid-connect/introduction/ | Logout-/Session-Management-Limits, keine pauschale Sitzungsrevocation |
| Authelia Token-API | https://github.com/authelia/authelia/blob/master/api/openapi.yml | Dokumentierte Tokenrevocation; konkrete Version erneut prüfen |
| Authelia Ereignismail | https://www.authelia.com/configuration/notifications/events/ | Sicherheitsereignisse an bestehende Adresse, tatsächliche Zustellung testen |
| Authelia Proxyheaders | https://www.authelia.com/integration/proxies/forwarded-headers/ | Forwarded-Headers ausschließlich vom eigenen Proxy übernehmen |
| Let's Encrypt Challenges | https://letsencrypt.org/docs/challenge-types/ | HTTP-01 Port 80, DNS-01 TXT-Eintrag; konkrete Wahl vor Rollout |
| Compose Secrets | https://docs.docker.com/compose/how-tos/use-secrets/ | Dateimounts, keine verschlüsselte Schlüsselverwaltung |
| Docker Portbindung | https://docs.docker.com/engine/network/port-publishing/ | Loopback explizit statt allgemeiner Hostbindung |
| Docker Compose Netze | https://docs.docker.com/compose/how-tos/networking/ | Private Netze ersetzen keine korrekten Published-Port-Regeln |
| PostgreSQL Rechte | https://www.postgresql.org/docs/current/sql-grant.html | Datenbank-/CONNECT-/PUBLIC-Rechte begrenzen |
| PostgreSQL18 Credentialfunktionen | https://www.postgresql.org/docs/18/sql-createfunction.html | Am2026-11-07 geprüft: sicherer Definer-search_path, PUBLIC-EXECUTE entziehen |
| PostgreSQL18 Credential-RLS | https://www.postgresql.org/docs/18/ddl-rowsecurity.html | Am2026-11-07 geprüft: FORCE-RLS, Owner-/Superusergrenzen und Default-deny |
| PostgreSQL18 Zeilensperren | https://www.postgresql.org/docs/18/explicit-locking.html | Am2026-11-07 geprüft: FOR UPDATE/CAS und FOR SHARE für aktive Bindungen |
| Cryptography AESGCM | https://cryptography.io/en/50.0.2/hazmat/primitives/aead/ | Authentifizierte Verschlüsselung, AAD, Nonces und InvalidTag; keine eigene Kryptografie |
| Cryptography Wheels | https://cryptography.io/en/50.0.2/installation/ | Gepinnte Binarywheels für CPython/Linux; separat installierter Credentialkern |
| Kryptografieabhängigkeiten | https://pypi.org/pypi/cryptography/json | Offizielle Version 50.0.2 und Wheelhashes; transitive Pins aus den entsprechenden cffi-/pycparser-Metadaten |
| RSI | https://www.tradingview.com/support/solutions/43000502338-relative-strength-index-rsi/ | Indikatorgrundlage, keine Freigabe zur Nutzung von TradingView-Marktfeeds |
| ATR | https://www.tradingview.com/support/solutions/43000501823-average-true-range-atr/ | Wilder/RMA als Berechnungsvariante |
| Supertrend | https://www.tradingview.com/support/solutions/43000634738-supertrend/ | Formel/Fliplogik; Implementierung mit eigenen Daten |
| Supertrend-Standardvergleich | https://help.ctrader.com/indicators/built-in/trend/supertrend/ | 10/3 als Vergleichsparameter, kein nachgewiesenes Optimum |
| ZITADEL Free | https://zitadel.com/pricing/detail | Freefeatures, Quoten und kurze Log-/Auditfristen |
| ZITADEL Mail | https://zitadel.com/docs/guides/manage/console/default-settings | Eingebauter SMTP für Evaluation, produktiven Mailweg klären |
| ZITADEL Datenschutz | https://zitadel.com/docs/legal/data-processing-agreement | Externe Verarbeitung vor Providerwahl prüfen |
| Keycloak Kapazität | https://www.keycloak.org/server/containers | 2 GB Empfehlung für kleinen produktionsfähigen IdP allein |
| authentik Kapazität | https://docs.goauthentik.io/install-config/install/docker-compose/ | Mindestens 2 CPU/2 GB Host-RAM |
| MT5 Python | https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py | Bindung an Terminalprozess |
| MT5 OrderSend | https://www.mql5.com/en/docs/trading/ordersend | Annahme ist kein vollständiger Fillnachweis |
| MT5 Events | https://www.mql5.com/en/docs/event_handlers/ontradetransaction | Tradeevents für Ausführungsabgleich |
| MT5 WebRequest | https://www.mql5.com/en/docs/network/webrequest | Synchron, erlaubte URL nötig, nicht im Strategy Tester |
| MT5 OnTimer | https://www.mql5.com/en/docs/event_handlers/ontimer | Laufende Timer blockieren neue Timerereignisse, keine garantierte Pollfrequenz |
| MT5 Account Properties | https://www.mql5.com/en/docs/constants/environment_state/accountinformation | Broker-Server/Login/Demomodus vor Dispatch prüfen |
| MT5 Symbolregeln | https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants | Lots, Stops, Handelsstatus und Kontrakte |
| Bitget Rechte | https://www.bitget.com/docs/classic/rest-api | Keyrechte, Passphrase und IP-Bindung |
| Bitget Classic-Identität | https://www.bitget.com/legacy-docs/classic/spot/account/Get-Account-Info | Signierte UID/Parent-UID, authorities und IP-Whitelist; keine UTA-permType-Felder |
| Bitget Classic-Konten | https://www.bitget.com/docs/catalog/classic-contract-account/classic-contract-account | Separate Futures-Equity/Margin und Produkttypen, keine Spotbudgetsumme |
| Bitget UTA | https://www.bitget.com/docs/uta/uta-intro | Accountmodi nicht implizit festlegen |
| Bitget Orders | https://www.bitget.com/docs/catalog/classic-contract-trade/classic-contract-trade | `clientOid`, Abfrage und Reduce-only-Besonderheiten |
| Bitget Positionen | https://www.bitget.com/docs/catalog/classic-contract-position/classic-contract-position | Margin, Liquidation und Positionsdaten |
| Bitget Liquidation | https://www.bitget.com/futures/introduction/liquidation-summarize | Markpreis und Maintenance-Risiko |
| Bitget Market | https://www.bitget.com/docs/catalog/classic-contract-market/classic-contract-market | Instrumentregeln und Fundingdaten |
| Bitget V3 Historie | https://www.bitget.com/docs/catalog/market/market-data#get-klinecandlestick-history | Öffentliches SPOT-H4: 100 Bars/Seite, maximal 90 Tage je Request, 20 Requests/s/IP; tatsächliche Zeitgrenzen am 2026-11-07 geprüft |
| FTMO Objectives | https://ftmo.com/en/trading-objectives/ | Kontoprofile/Phasen unterscheiden sich bei Verlustregeln |
| FTMO News | https://ftmo.com/en/faq/can-i-trade-news/ | Restriktionen abhängig von Phase/Konto |
| FTMO Swing | https://ftmo.com/en/faq/ftmo-swing-account-type/ | Separates Profil nötig |
| FTMO Personal Use | https://ftmo.com/en/forbidden-trading-practices/ | Drittzugriff und übermäßige Handelsänderungen prüfen |
| Alpha Vantage | https://www.alphavantage.co/support/ | Free derzeit 25 Requests/Tag; kein vollwertiger Livefeed |
| Twelve Data Preise | https://twelvedata.com/pricing | Basic derzeit 8 APIcredits/Minute, 800/Tag; Entitlements beachten |
| Twelve Data Credits | https://support.twelvedata.com/en/articles/5615854-credits | Gewicht pro Endpoint/Symbol und Quotenreset |
| TradingView API | https://www.tradingview.com/support/solutions/43000474413-i-need-access-to-your-api-in-order-to-get-data-or-indicator-values/ | Kein allgemeiner Nutzerdaten-API-Zugang |
| TradingView Terms | https://www.tradingview.com/policies/ | Display-/Non-display-Nutzung einschließlich automatisierten Handels beschränkt |
| Marke | https://www.investalo.de/ | Geforderte Stylingreferenz, keine fertige Designspezifikation |

## Auswirkungen auf den Entwurf

- RLS ergänzt Autorisierung; ein privilegierter Backenddienst bleibt eine eigene
  Sicherheitsgrenze.
- Outbox und Command-IDs unterstützen Konsistenz, versprechen aber keine
  Exactly-once-Ausführung beim Broker.
- MT5 braucht einen verfügbaren Terminalhost, keinen generischen REST-Adapter
  ohne lokale Laufzeit.
- Marginstress muss aktuelle Brokerregeln verwenden; die Beispielrechnung ist
  keine Liquidationsgarantie.
- TradingView Essentials wird nicht als genehmigter Feed für automatischen
  Handel eingeplant. Vertrags-/Anbieterprüfung wäre dafür erforderlich.
- Free-Datenabos begrenzen Abdeckung und Frequenz. Für Mehrnutzeranzeige und
  Kundendienstleistungen sind Nutzungs-/Redistributionsrechte separat zu prüfen.

Die konsultierte Outbox-Dokumentation begründet ein Muster, keine Auswahl von AWS
als Infrastruktur. Ebenso ist die Nennung einer Chart-/Authlösung noch keine
Installation oder Providerfreigabe.
