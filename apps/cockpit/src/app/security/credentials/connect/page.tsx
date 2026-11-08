import Link from "next/link";
import { getSession } from "@/lib/auth";
import { getPasskeyContext } from "@/lib/passkey-enrollment";
import { listCredentialMetadata } from "@/lib/credential-step-up";
import { credentialBrowserRuntimeAvailable } from "@/lib/passkey-credential-browser-server";
import { BackendError } from "@/lib/backend";
import type { CredentialActionMetadata } from "@/lib/credential-action-contracts";
import { Shell } from "@/components/dashboard";
import { Login } from "@/components/login";
import { PasskeyCredentialForm } from "@/components/passkey-credential-form";

export const dynamic = "force-dynamic";
export default async function Page() {
  const session = await getSession();
  if (!session) return <Login />;
  let accounts: CredentialActionMetadata[] | null = null, registered = false;
  const enabled = credentialBrowserRuntimeAvailable();
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
    <Link href="/security/credentials" className="detail-back">← Kontozugänge</Link>
    <section className="panel">
      <div className="section-heading"><h2>Bitget-Zugang verbinden</h2><span className="badge neutral">LESEZUGRIFF</span></div>
      <p className="panel-intro">Wähle dein Konto und die gewünschte Änderung. Nach der Passkey-Prüfung bestätigst du die angezeigte Kontoänderung ausdrücklich.</p>
      {!enabled ? <p role="status">Die Kontoanbindung ist in dieser Umgebung noch nicht freigeschaltet.</p>
        : !registered ? <p role="status">Für eine Kontoänderung benötigst du einen aktiven Passkey. Prüfe zuerst deinen Status in der Passkey-Verwaltung.</p>
          : accounts === null ? <p role="status">Der aktuelle Kontostand ist nicht bestätigt. Lade den Status neu.</p>
            : <PasskeyCredentialForm csrf={session.csrf} accounts={accounts} />}
      <Link href="/security/passkeys" className="button secondary">Passkey verwalten</Link>
    </section>
  </Shell>;
}
