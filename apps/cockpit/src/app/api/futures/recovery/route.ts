import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { getConfig } from "@/lib/config";
import { apiRequest, BackendError } from "@/lib/backend";
import { limitedBody, requireCsrf, requireSameOrigin } from "@/lib/security";
import { parseRecoveryRequest, parseRecoveryStatus } from "@/lib/futures-recovery-contracts";

export async function POST(request: NextRequest) {
  const headers = { "Cache-Control": "no-store" };
  // Separate opt-in; default/public deployment and Spot paper stay untouched.
  if (process.env.COCKPIT_FUTURES_RECOVERY_PREVIEW !== "1")
    return NextResponse.json({ error: "Futures-Freigabe noch nicht verfügbar." }, { status: 404, headers });
  try {
    requireSameOrigin(request, (await getConfig()).origin);
    const session = await getSession();
    if (!session) return NextResponse.json({ error: "Bitte erneut anmelden." }, { status: 401, headers });
    requireCsrf(session.csrf, request.headers.get("x-csrf-token"));
    if (request.headers.get("content-type")?.split(";")[0] !== "application/json") throw new Error("BODY_REJECTED");
    const data = parseRecoveryRequest(JSON.parse(await limitedBody(request, 4096)));
    const result = await apiRequest(session, "/v1/futures-recovery", {
      method: "POST", body: JSON.stringify(data), idempotencyKey: data.event_id,
    });
    return NextResponse.json(parseRecoveryStatus(result, session.tenantId), { headers });
  } catch (error) {
    return NextResponse.json({ error: "Freigabe nicht bestätigt. Aktuellen Status neu laden." },
      { status: error instanceof BackendError ? error.status : 400, headers });
  }
}
