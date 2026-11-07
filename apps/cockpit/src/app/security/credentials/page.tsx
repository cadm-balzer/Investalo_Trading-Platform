import Link from "next/link";
import { getSession } from "@/lib/auth";
import { listCredentialMetadata } from "@/lib/credential-step-up";
import { BackendError } from "@/lib/backend";
import type { CredentialActionMetadata } from "@/lib/credential-action-contracts";
import { Shell } from "@/components/dashboard";
import { Login } from "@/components/login";
import { CredentialActionForm } from "@/components/credential-action-form";

export const dynamic = "force-dynamic";

export default async function Page() {
  const session = await getSession();
  if (!session) return <Login />;
  let accounts: CredentialActionMetadata[] | null = null;
  try {
    accounts = await listCredentialMetadata(session);
  } catch (error) {
    if (error instanceof BackendError && [401, 403].includes(error.status)) return <Login expired />;
  }
  return <Shell session={session} section="shield" connected={accounts !== null}>
    <Link href="/security" className="detail-back">← Sicherheit</Link>
    <section className="panel">
      <div className="section-heading"><h2>Bitget-Zugang bewusst bestätigen</h2><span className="badge neutral">LESEZUGRIFF</span></div>
      <p className="panel-intro">Hier siehst du deine zugeordneten Konten und die vorgesehenen Aktionen. Der Bestätigungsschritt bleibt gesperrt, solange der zusätzliche Nachweis eines frischen zweiten Faktors fehlt.</p>
      {accounts === null ? <div className="connection-error" role="status">
        <h3>Kontostand nicht bestätigt</h3><p>Die geschützten Kontometadaten sind aktuell nicht verfügbar. Eine neue Aktion kann erst nach einer bestätigten Antwort gestartet werden.</p>
        <Link href="/security/credentials" className="button secondary">Erneut laden</Link>
      </div> : <CredentialActionForm csrf={session.csrf} accounts={accounts} />}
    </section>
    <section className="panel">
      <h2>Kontoanbindung noch nicht verfügbar</h2>
      <p className="panel-intro">Kontometadaten sind sichtbar. Zusätzliche Bestätigung, API-Schlüsseleingabe und Kontoänderungen bleiben gesperrt.</p>
    </section>
  </Shell>;
}
