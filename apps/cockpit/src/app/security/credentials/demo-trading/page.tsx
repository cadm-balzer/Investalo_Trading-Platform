import Link from "next/link";
import { getSession } from "@/lib/auth";
import { getPasskeyContext } from "@/lib/passkey-enrollment";
import {
  demoTradingCredentialBrowserRuntimeAvailable, listDemoTradingCredentialMetadata,
} from "@/lib/demo-trading-passkey-credential-browser-server";
import { BackendError } from "@/lib/backend";
import type { DemoTradingCredentialActionMetadata } from "@/lib/demo-trading-credential-action-contracts";
import { Shell } from "@/components/dashboard";
import { Login } from "@/components/login";
import { DemoTradingPasskeyCredentialForm } from "@/components/demo-trading-passkey-credential-form";
import { BitgetDemoTradingSetupStatus } from "@/components/bitget-demo-trading-access";

export const dynamic = "force-dynamic";
export default async function Page() {
  const session = await getSession();
  if (!session) return <Login />;
  let accounts: DemoTradingCredentialActionMetadata[] | null = null, registered = false;
  const enabled = await demoTradingCredentialBrowserRuntimeAvailable();
  if (enabled) {
    try {
      const context = await getPasskeyContext(session);
      registered = context.credential?.status === "active" && context.credential.enrollment_epoch === session.authEpoch;
      if (registered) accounts = await listDemoTradingCredentialMetadata(session);
    } catch (error) {
      if (error instanceof BackendError && [401, 403].includes(error.status)) return <Login expired />;
    }
  }
  return <Shell session={session} section="shield" connected={accounts !== null}>
    <Link href="/security/credentials" className="detail-back">← Kontozugänge</Link>
    <section className="panel">
      <div className="section-heading"><h2>Bitget-Demo-Handelszugang einrichten</h2><span className="badge neutral">{enabled ? "DEMO · FUTURES/SPOT" : "EINRICHTUNG AUSSTEHEND"}</span></div>
      {enabled && <p className="panel-intro">Hinterlege den im Bitget-Demo-Modus erstellten API-Key, Secret und Passphrase. Nach der Passkey-Prüfung bestätigst du die Einrichtung.</p>}
      {!enabled ? <BitgetDemoTradingSetupStatus />
        : !registered ? <p role="status">Für eine Kontoänderung benötigst du einen aktiven Passkey. Prüfe zuerst deinen Status in der Passkey-Verwaltung.</p>
          : accounts === null ? <p role="status">Der aktuelle DemoTrading-Kontostand ist nicht bestätigt. Lade den Status neu.</p>
            : <DemoTradingPasskeyCredentialForm csrf={session.csrf} accounts={accounts} />}
      <Link href="/security/passkeys" className="button secondary">Passkey verwalten</Link>
    </section>
  </Shell>;
}
