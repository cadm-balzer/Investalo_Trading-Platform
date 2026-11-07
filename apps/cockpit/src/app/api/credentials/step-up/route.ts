import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { getConfig } from "@/lib/config";
import { credentialAction, parseAccountRequest } from "@/lib/credential-action-contracts";
import { limitedBody, requireCsrf, requireSameOrigin } from "@/lib/security";

export async function POST(request: NextRequest) {
  const headers = { "Cache-Control": "no-store" };
  try {
    requireSameOrigin(request, (await getConfig()).origin);
    const session = await getSession();
    if (!session) return NextResponse.json({ error: "Bitte erneut anmelden." }, { status: 401, headers });
    requireCsrf(session.csrf, request.headers.get("x-csrf-token"));
    if (request.headers.get("content-type")?.split(";")[0] !== "application/json") throw new Error("BODY_REJECTED");
    const data = JSON.parse(await limitedBody(request)) as Record<string, unknown>;
    if (!data || typeof data !== "object" || Array.isArray(data) ||
      Object.keys(data).length !== 2 || !("action" in data) || !("platform_account_id" in data)) throw new Error("BODY_REJECTED");
    parseAccountRequest({ platform_account_id: data.platform_account_id });
    credentialAction(data.action);
  } catch {
    return NextResponse.json({ error: "Anfrage abgelehnt." }, { status: 400, headers });
  }
  // No IdP redirect or grant from auth_time + amr alone.
  return NextResponse.json({ error: "Frischer zweiter Faktor noch nicht verfügbar." }, { status: 503, headers });
}
