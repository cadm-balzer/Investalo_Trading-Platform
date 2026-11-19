import Link from "next/link";
import { notFound } from "next/navigation";
import { getSession } from "@/lib/auth";
import { adminMailAvailable, adminMailSummary } from "@/lib/admin-mail-server";
import { Shell } from "@/components/dashboard";
import { Login } from "@/components/login";
import { AdminMailForm } from "@/components/admin-mail-form";

export const dynamic = "force-dynamic";
export default async function Page() {
  const session = await getSession();
  if (!session) return <Login />;
  if (!await adminMailAvailable(session)) notFound();
  const summary = await adminMailSummary(session);
  return <Shell session={session} section="shield" connected>
    <Link className="detail-back" href="/security">← Sicherheit</Link>
    <section className="panel">
      <div className="section-heading"><h2>Administration · Systemeinstellungen</h2><span className="badge neutral">ADMIN</span></div>
      <p className="panel-intro">Hier verwaltest du den E-Mail-Versand für das Cockpit. Speichere die SMTP-Einstellungen und bestätige anschließend deine E-Mail-Adresse.</p>
      <AdminMailForm csrf={session.csrf} initial={summary} />
    </section>
  </Shell>;
}
