import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { apiRequest, BackendError } from "@/lib/backend";
import { getConfig } from "@/lib/config";
import { limitedBody, requireCsrf, requireSameOrigin } from "@/lib/security";
import { parseBacktestRequest, parseJobResponse } from "@/lib/backtest-contracts";

export async function POST(request: NextRequest) {
  try {
    requireSameOrigin(request, (await getConfig()).origin);
    const session = await getSession();
    if (!session) return NextResponse.json({ error: "Bitte erneut anmelden." }, { status: 401 });
    requireCsrf(session.csrf, request.headers.get("x-csrf-token"));
    if (request.headers.get("content-type")?.split(";")[0] !== "application/json") throw new Error("BODY_REJECTED");
    const raw = await limitedBody(request);
    const data = parseBacktestRequest(JSON.parse(raw));
    const idempotencyKey = request.headers.get("idempotency-key") ?? "";
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(idempotencyKey)) throw new Error("IDEMPOTENCY_REJECTED");
    const result = await apiRequest(session, "/v1/backtests", {
      method: "POST", body: JSON.stringify(data), idempotencyKey,
    });
    return NextResponse.json(parseJobResponse(result, session.tenantId), { status: 202, headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    const status = error instanceof BackendError ? error.status : 400;
    return NextResponse.json({ error: status === 401 ? "Sitzung nicht mehr gültig. Bitte erneut anmelden." :
      status === 409 ? "Kein passender unveränderlicher Datensatz verfügbar oder Auftragsschlüssel bereits verwendet. Auswahl prüfen." :
        "Auftrag nicht bestätigt. Es wurde kein Ergebnis bestätigt." }, { status, headers: { "Cache-Control": "no-store" } });
  }
}
