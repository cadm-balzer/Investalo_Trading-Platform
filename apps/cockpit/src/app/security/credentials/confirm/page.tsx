import Link from "next/link";
import { getSession } from "@/lib/auth";
import { getCredentialGrant } from "@/lib/credential-step-up";
import { parseActionTarget } from "@/lib/credential-action-contracts";
import { Shell } from "@/components/dashboard";
import { Login } from "@/components/login";
import { CredentialConfirmationForm, type CredentialGrantView } from "@/components/credential-confirmation-form";

export const dynamic = "force-dynamic";

export default async function Page() {
  const session = await getSession();
  if (!session) return <Login />;
  let grant: CredentialGrantView | null = null;
  try {
    const current = await getCredentialGrant();
    if (current && /^[A-Za-z0-9_-]{43}$/.test(current.confirmationToken)) {
      // Explicit public projection prevents future private grant fields from
      // being serialized across the server/client component boundary.
      grant = { target: parseActionTarget(current.target), accountName: current.accountName,
        expiresAt: current.expiresAt, confirmationToken: current.confirmationToken };
    }
  } catch { grant = null; }
  return <Shell session={session} section="shield" connected={grant !== null}>
    <Link href="/security/credentials" className="detail-back">← Kontenauswahl</Link>
    <section className="panel">
      <div className="section-heading"><h2>Festgelegte Aktion prüfen</h2><span className="badge neutral">BEWUSSTE BESTÄTIGUNG</span></div>
      {grant ? <CredentialConfirmationForm csrf={session.csrf} grant={grant} /> : <div className="connection-error" role="status">
        <h3>Bestätigung derzeit gesperrt</h3>
        <p>Es liegt keine nutzbare Bestätigung vor. Der zusätzliche Nachweis eines frischen zweiten Faktors ist noch nicht verfügbar; Kontoänderungen bleiben gesperrt.</p>
        <Link href="/security/credentials" className="button secondary">Kontometadaten ansehen</Link>
      </div>}
    </section>
  </Shell>;
}
