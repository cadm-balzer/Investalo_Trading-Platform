# Passkey-Prüfseite und BFF-Durchlauf

Stand 2026-11-08. IP-037 verbindet den dauerhaften Nachweis007 mit einer
separaten Prüfseite unter `/security/passkeys/verify`. Sie zeigt Konto und
Aktion, fordert anschließend eine frische Passkey-Assertion an und lässt
genau diese Vorschau einmalig bestätigen. Alle Antworten melden
`execution_enabled:false`;003/004, Keyeingabe und Kontoänderungen bleiben gesperrt.

## Freigabegrenze

Die vier POST-Routen `/api/passkeys/actions/{start,finish,grant,confirm}`
und die Prüfoberfläche benötigen ausdrücklich
`COCKPIT_PASSKEY_PROOF_PREVIEW=1`. Ohne Opt-in liefern die Routen503.
Default-Compose und öffentliche Vorschau setzen dieses Flag nicht.
Die laufenden öffentlichen Container wurden für diesen Checkpoint nicht geändert.

Jede Anfrage verlangt den exakten HTTPS-Origin, `Sec-Fetch-Site:same-origin`,
aktuelle Sitzung/CSRF und begrenztes JSON ohne doppelte Felder.
Die unveränderliche Sitzung, deren CSRF geprüft wurde, wird dem Serveradapter
mitgegeben. Körperlesen, Kryptografie und API-Aufrufe dürfen keine neu erfasste
Anmeldung verwenden. Identität, Epoch, ursprüngliche OIDC-Zeit, CSRF, Origin,
Sitzungsfrist und Opt-in werden vor Veröffentlichung nochmals geprüft.

Nur sichere Konto-/Aktionsdaten, WebAuthn-Requestoptionen und die eigene
kurzlebige Vorschaukennung gelangen in den Browser. Credentialrecords,
Publickeys, Bindungshashes und Brokerdaten werden nicht serialisiert.
Abbruch oder unbekannter Commit führt zu keiner automatischen Wiederholung.
Vorschaukennungen bleiben nur im Zustand der jeweiligen Seite, ohne URL,
Cookie, localStorage oder sessionStorage.

## Registrierung und Prüfbelege

Der vollständige Enrollmentablauf ist als injizierbare Orchestrierung getrennt
und behält den verschlüsselten atomaren Versuchsspeicher. Sitzung/Origin und
ursprüngliche Sitzungsfrist bleiben über alle asynchronen Schritte gebunden.
Erfolg verlangt nach dem Write eine aktuelle API-Lesebestätigung des exakt
gespeicherten Faktors. Ältere, höchstens120 Sekunden gültige Versuche ohne
`sessionExpiresAt` werden nach dem Update geschlossen abgewiesen.

265 Cockpitprüfungen bestanden: darunter64 neue HTTP-Grenzfälle,44 vollständige
synthetische Enrollmentabläufe und14 Browserprojektion-/P256-Fälle.
Typecheck und gepinnter Cockpitbuild sind grün.
Die separate [Prüfumgebung](../infra/README.md#isolierte-passkey-browserprüfung)
verwendet echte HTTPS/BFF/API/PG-Verbindungen mit synthetischen P256-Schlüsseln,
eigenen Testschlüsseln und ausdrücklich synthetischer administrativer Freigabe.
90 aktivierte und9 deaktivierte HTTPS-Prüfpunkte bestanden; die deaktivierte
Oberfläche verändert weder Faktoren noch Nachweise. Acht Vorbereitungstests
prüfen Besitz/Rechte, Symlinks/Hardlinks und einen ersetzten Elternpfad.
Privilegierte Vorbereitung arbeitet ausschließlich über gehaltene
Verzeichnisdeskriptoren. Unabhängiger Review nach den Korrekturen ohne Restblocker.
Testdienste sind angehalten; die öffentliche Vorschau blieb gesund (TLS200).
API/SQL und Abhängigkeiten sind unverändert; historische IP-036-Tests wurden
für diesen Checkpoint nicht erneut gezählt.

Diese Belege ersetzen weder den tatsächlichen `navigator.credentials`-Aufruf
auf einem physischen Gerät noch die manuell bestätigte Nutzer-E-Mail.
Öffentliche Geräteabnahme, Credentialfreigabe, Recovery und Pilotbetrieb
bleiben eigene Schritte in IP-033 und BL-020/021/025.

Grundlagen: [W3C WebAuthn3](https://www.w3.org/TR/webauthn-3/),
[OWASP CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html),
[interner Nachweis007](passkey-action-proofs.md).
