import Link from "next/link";
import { getSession } from "@/lib/auth";
import { getPasskeyContext } from "@/lib/passkey-enrollment";
import { listCredentialMetadata } from "@/lib/credential-step-up";
import { passkeyProofPreviewEnabled } from "@/lib/passkey-action-preview";
import { BackendError } from "@/lib/backend";
import type { CredentialActionMetadata } from "@/lib/credential-action-contracts";
import { Shell } from "@/components/dashboard";
import { Login } from "@/components/login";
import { PasskeyProofForm } from "@/components/passkey-proof-form";

export const dynamic = "force-dynamic";
export default async function Page() {
  const session = await getSession();
  if (!session) return <Login />;
  let accounts: CredentialActionMetadata[] | null = null, registered = false;
  const enabled = passkeyProofPreviewEnabled();
  if (enabled) {
    try {
      const context = await getPasskeyContext(session);
      registered = context.credential?.status === "active" && context.credential.enrollment_epoch === session.authEpoch;
      if (registered) accounts = await listCredentialMetadata(session);
    } catch (error) {
      if (error instanceof BackendError && [401, 403].includes(error.status)) return <Login expired />;
    }
  }
  return <Shell session={session} section="shield" connected={accounts !== null}>
    <Link href="/security/passkeys" className="detail-back">← Passkey verwalten</Link>
    <section className="panel">
      <div className="section-heading"><h2>Passkey-Bestätigung prüfen</h2><span className="badge neutral">FUNKTIONSPRÜFUNG</span></div>
      <p className="panel-intro">Wähle ein zugeordnetes Konto und eine Aktion. Danach bestätigt dein Gerät deinen Passkey für genau diese Vorschau. Die Prüfung führt keine Kontoänderung aus.</p>
      {!enabled ? <p role="status">Die Bestätigungsprüfung ist in dieser Umgebung noch nicht freigeschaltet.</p>
        : !registered ? <p role="status">Für die Prüfung benötigst du einen aktiven registrierten Passkey. Prüfe zuerst den Status in der Passkey-Verwaltung.</p>
          : accounts === null ? <p role="status">Der aktuelle Kontostand ist nicht bestätigt. Lade den Status neu, bevor du eine Prüfung beginnst.</p>
            : <PasskeyProofForm csrf={session.csrf} accounts={accounts} />}
    </section>
  </Shell>;
}
