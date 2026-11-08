import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { getConfig } from "@/lib/config";
import { assertAuthorizedSession, snapshotAuthorizedSession } from "@/lib/authorized-session";
import { beginPasskeyEnrollment } from "@/lib/passkey-enrollment";
import { exactObject, parseEnrollmentJson } from "@/lib/passkey-enrollment-state";
import { limitedBody, requireCsrf, requireSameOrigin } from "@/lib/security";

export async function POST(request: NextRequest) {
  const headers = { "Cache-Control": "no-store" };
  try {
    const origin = (await getConfig()).origin;
    requireSameOrigin(request, origin);
    const session = await getSession();
    if (!session) return NextResponse.json({ error: "Bitte erneut anmelden." }, { status: 401, headers });
    const authorized = snapshotAuthorizedSession(session);
    requireCsrf(authorized.csrf, request.headers.get("x-csrf-token"));
    if (request.headers.get("content-type")?.split(";")[0] !== "application/json") throw new Error("BODY_REJECTED");
    const data = exactObject(parseEnrollmentJson(await limitedBody(request, 1024)), ["token"]);
    if ((await getConfig()).origin !== origin) throw new Error("ORIGIN_REJECTED");
    const result = await beginPasskeyEnrollment(data.token, authorized);
    if ((await getConfig()).origin !== origin) throw new Error("ORIGIN_REJECTED");
    const latest = await getSession();
    if (!latest) throw new Error("SESSION_REJECTED");
    assertAuthorizedSession(authorized, latest);
    return NextResponse.json(result, { headers });
  } catch {
    return NextResponse.json({ error: "Registrierung nicht gestartet. Ticket, Sitzung oder Berechtigung prüfen." }, { status: 400, headers });
  }
}
