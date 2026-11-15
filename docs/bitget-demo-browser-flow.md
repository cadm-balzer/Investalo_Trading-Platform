# Geschützter eigener Demo-Browserablauf

Stand 2026-11-15, IP-009/IP-015. PR84 (`36adb95`) ist in
`1661ca3` enthalten; GitHub/Fetch/Ancestry bestätigt.

Der [Demo-Metadaten-/Serveradapter](bitget-demo-metadata-provider.md) erhält
einen eigenen Browservertrag, Controller, Formular und Next-Routen.
Die Seite `/security/credentials/demo` ist über die Credentialseite verlinkt.
Der operative Browserprovider bleibt ausdrücklich nicht verfügbar:
`demoCredentialBrowserRuntimeAvailable()` liefert fest `false`.
Die Seite zeigt den fehlenden Zugang; sie lädt dann keine Kontometadaten und
rendert keine Keyfelder. Keine Umgebungsvariable aktiviert diesen Provider.

## Ablauf und Grenzen

Die eigenen POST-Pfade
`/api/credentials/bitget-demo/passkey/{start,finish,execute}` erlauben
ausschließlich `register` oder `revoke`, feste Keyrevision1 und den Consent
`demo-credential-write`. Normalpfade, Replacement, zusätzliche Felder,
Query-/kodierte Pfadvarianten und abweichende Projektionen werden abgewiesen.
Originalsitzung, OIDC-Zeit, Tenant/Epoch, CSRF, HTTPS-Origin und aktuelle
Readbacks bleiben erforderlich. Default-off wird vor Body-/Config-/Sessionread
geprüft. Bodygröße16KiB, gesamte Lesedauer10s, UTF8 und doppelte Felder sind
begrenzt beziehungsweise strikt validiert.

Der eigene Continuationadapter reserviert Kapazität vor jedem Providerawait.
Standard32 globale/zwei sitzungsgebundene Leases, höchstens128/acht und120s,
zusätzlich begrenzt durch die ursprüngliche Sitzung. Prepared/Granted-Handles
wechseln einmalig; eine fremde Sitzung kann den Originalhandle nicht verbrauchen.
Laufende Arbeit behält ihren Platz bis zum tatsächlichen Abschluss.
Private Triple, Body und JWT werden nicht in Handles oder Browserstorage
geschrieben. Durable015/016 bleiben die Autorität; Neustart oder ein anderer
Adapter erzeugen keine Wiederholungsfreigabe.

Die vertrauenswürdige `acceptCredentials`-Policy ist zwingend injiziert.
Die jetzige Formularabnahme erlaubt ausschließlich synthetische Testdaten.
Ein echtes Provisioning-/Signing-/TLSsetup folgt separat; Flags oder Angaben
im Browser belegen keine Demo-Key-/UID-Provenienz.

Das Formular prüft aktuelle Konto-/Verbindungsmetadaten: Registrierung nur
bei freiem, bereitem Konto; Widerruf einer aktiven eigenen Connection auch
bei pausiertem Konto. Widerrufene/erschöpfte Verbindungen bieten keine Aktion.
Nach Prepare werden Passwortfelder geleert; Passkeyprüfung zeigt die gebundene
Vorschau, erst danach folgt die ausdrückliche Bestätigung. Abbruch, Ablauf,
Tab-/Lifecyclewechsel und ungewisser Abschluss geben keine automatische
Wiederholung frei. Controllerreferenzen und DOMfelder werden freigegeben;
garantiertes Überschreiben des JavaScriptheaps wird nicht behauptet.

## Abnahme

101 neue Prüfungen und die vollständige gepinnte Cockpit-Regression:
881 Fälle, alle grün. Zwei Request/Response-Abläufe verbinden den eigenen
HTTPadapter, Continuations, tatsächlich generierte P256/WebAuthn-Signaturen,
Demo-BFF/Consent und genau einen injizierten synthetischen Executordispatch.
Replay, Fremdsitzung, Kapazität während Await, Expiry, Abbruch und ungewisser
Abschluss werden geprüft. React-SSR prüft das tatsächliche Formular und die
Seite; Next-Routen und der feste abgeschaltete Serverwrapper werden geprüft.
Typecheck und gepinnter Cockpitbuild bestehen.

Das sind In-Process-/SSRprüfungen mit synthetischen privaten Adaptern.
Eine kombinierte laufende HTTPS/BFF/API/PG/Executorabnahme, ein physischer
Authenticator und native Demo-Key-/Readabnahme sind noch offen.
Bestehende001–017 sowie Entwicklungsmigrationsset bleiben unverändert;
keine Migration, Dependencies, normalen Services, echten Keys, Brokerrequests,
Orders, Backtests, öffentliche Aktivierung, Livehandel oder KI geändert.

Als Nächstes eigene private Signing-/Executor-/Provisioningidentität installieren
und den vollständigen Ablauf in einer isolierten lokalen Umgebung abnehmen.
Anschließend native Demo-Keybindung und Readabnahme, danach gebundener
Ordertransport und vollständige Kosten-/Orderreconciliation.
