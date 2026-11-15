import Link from "next/link";
import { getSession } from "@/lib/auth";
import { getPasskeyContext } from "@/lib/passkey-enrollment";
import {
  demoCredentialBrowserRuntimeAvailable, listDemoCredentialMetadata,
} from "@/lib/demo-passkey-credential-browser-server";
import { BackendError } from "@/lib/backend";
import type { DemoCredentialActionMetadata } from "@/lib/demo-credential-action-contracts";
import { Shell } from "@/components/dashboard";
import { Login } from "@/components/login";
import { DemoPasskeyCredentialForm } from "@/components/demo-passkey-credential-form";

export const dynamic = "force-dynamic";
export default async function Page() {
  const session = await getSession();
  if (!session) return <Login />;
  let accounts: DemoCredentialActionMetadata[] | null = null, registered = false;
  const enabled = demoCredentialBrowserRuntimeAvailable();
  if (enabled) {
    try {
      const context = await getPasskeyContext(session);
      registered = context.credential?.status === "active" && context.credential.enrollment_epoch === session.authEpoch;
      if (registered) accounts = await listDemoCredentialMetadata(session);
    } catch (error) {
      if (error instanceof BackendError && [401, 403].includes(error.status)) return <Login expired />;
    }
  }
  return <Shell session={session} section="shield" connected={accounts !== null}>
    <Link href="/security/credentials" className="detail-back">← Kontozugänge</Link>
    <section className="panel">
      <div className="section-heading"><h2>Bitget-Demo-Zugang verbinden</h2><span className="badge neutral">DEMO · LESEZUGRIFF</span></div>
      <p className="panel-intro">Wähle dein Demo-Konto und die gewünschte Änderung. Nach der Passkey-Prüfung bestätigst du die angezeigte Aktion ausdrücklich.</p>
      {!enabled ? <p role="status">Die Demo-Kontoanbindung ist in dieser Umgebung noch nicht freigeschaltet.</p>
        : !registered ? <p role="status">Für eine Kontoänderung benötigst du einen aktiven Passkey. Prüfe zuerst deinen Status in der Passkey-Verwaltung.</p>
          : accounts === null ? <p role="status">Der aktuelle Demo-Kontostand ist nicht bestätigt. Lade den Status neu.</p>
            : <DemoPasskeyCredentialForm csrf={session.csrf} accounts={accounts} />}
      <Link href="/security/passkeys" className="button secondary">Passkey verwalten</Link>
    </section>
  </Shell>;
}
