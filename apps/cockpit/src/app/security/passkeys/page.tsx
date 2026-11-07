import Link from "next/link";
import { getSession } from "@/lib/auth";
import { getPasskeyContext } from "@/lib/passkey-enrollment";
import type { PasskeyContext } from "@/lib/passkey-enrollment-state";
import { BackendError } from "@/lib/backend";
import { Shell } from "@/components/dashboard";
import { Login } from "@/components/login";
import { PasskeyEnrollmentForm } from "@/components/passkey-enrollment-form";

export const dynamic = "force-dynamic";
export default async function Page() {
  const session = await getSession();
  if (!session) return <Login />;
  let context: PasskeyContext | null = null;
  try { context = await getPasskeyContext(session); }
  catch (error) {
    if (error instanceof BackendError && [401, 403].includes(error.status)) return <Login expired />;
  }
  return <Shell session={session} section="shield" connected={context !== null}>
    <Link href="/security" className="detail-back">← Sicherheit</Link>
    <section className="panel">
      <div className="section-heading"><h2>Dein Passkey</h2><span className="badge neutral">PILOT</span></div>
      <p className="panel-intro">Der Passkey ist für die zusätzliche Bestätigung wichtiger Kontoänderungen vorgesehen.</p>
      {context === null ? <div className="connection-error" role="status"><h3>Status nicht bestätigt</h3>
        <p>Die geschützte Passkey-Verwaltung ist aktuell nicht verfügbar.</p></div>
        : context.credential === null ? <PasskeyEnrollmentForm csrf={session.csrf} />
          : context.credential.status === "revoked" ? <p role="status">Dieser Passkey wurde widerrufen. Wende dich für die Wiederherstellung an die Administration.</p>
            : <p role="status">Dein Passkey ist registriert.</p>}
    </section>
    <section className="panel"><h2>Kontoänderungen noch gesperrt</h2>
      <p className="panel-intro">Die zusätzliche Bestätigung wird im nächsten Schritt angebunden. Eine Registrierung startet keine Kontoanbindung und keinen Handel.</p>
      <Link href="/security/credentials" className="button secondary">Kontometadaten ansehen</Link>
    </section>
  </Shell>;
}
