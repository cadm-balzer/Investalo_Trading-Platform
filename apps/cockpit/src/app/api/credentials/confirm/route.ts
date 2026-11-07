import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { getConfig } from "@/lib/config";
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
    if (!data || typeof data !== "object" || Array.isArray(data) || Object.keys(data).length !== 2 ||
      data.confirmed !== true || typeof data.confirmation_token !== "string" ||
      !/^[A-Za-z0-9_-]{43}$/.test(data.confirmation_token)) throw new Error("BODY_REJECTED");
  } catch {
    return NextResponse.json({ error: "Anfrage abgelehnt." }, { status: 400, headers });
  }
  // Authentication/CSRF never replace proof of a newly used second factor.
  return NextResponse.json({ error: "Frischer zweiter Faktor noch nicht verfügbar." }, { status: 503, headers });
}
