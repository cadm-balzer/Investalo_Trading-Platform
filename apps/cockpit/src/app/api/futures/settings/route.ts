import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { getConfig } from "@/lib/config";
import { apiRequest, BackendError } from "@/lib/backend";
import { limitedBody, requireCsrf, requireSameOrigin } from "@/lib/security";
import { parseBasketSettings, parseBasketSettingsRequest } from "@/lib/futures-paper-settings-contracts";

export async function POST(request: NextRequest) {
  const headers = { "Cache-Control": "no-store" };
  if (process.env.COCKPIT_FUTURES_PAPER_SETTINGS_PREVIEW !== "1")
    return NextResponse.json({ error: "Futures-Planung noch nicht verfügbar." }, { status: 404, headers });
  try {
    requireSameOrigin(request, (await getConfig()).origin);
    const session = await getSession();
    if (!session) return NextResponse.json({ error: "Bitte erneut anmelden." }, { status: 401, headers });
    requireCsrf(session.csrf, request.headers.get("x-csrf-token"));
    if (request.headers.get("content-type")?.split(";")[0] !== "application/json") throw new Error("BODY_REJECTED");
    const { account_id, ...body } = parseBasketSettingsRequest(JSON.parse(await limitedBody(request, 1024)));
    const result = parseBasketSettings(await apiRequest(session, `/v1/futures-paper-settings/${account_id}`,
      { method: "POST", body: JSON.stringify(body) }), session.tenantId);
    if (result.accounts.length !== 1 || result.accounts[0].account_id !== account_id ||
      result.accounts[0].revision !== body.expected_revision+1 ||
      result.accounts[0].basket_limit !== body.basket_limit) throw new Error("WRITE_NOT_CONFIRMED");
    return NextResponse.json(result, { headers });
  } catch (error) {
    return NextResponse.json({ error: "Speichern nicht bestätigt. Kontoeinstellung neu laden." },
      { status: error instanceof BackendError ? error.status : 400, headers });
  }
}
