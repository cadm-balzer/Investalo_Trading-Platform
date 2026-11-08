import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { getConfig } from "@/lib/config";
import { assertAuthorizedSession, snapshotAuthorizedSession } from "@/lib/authorized-session";
import { finishPasskeyEnrollment } from "@/lib/passkey-enrollment";
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
    const data = exactObject(parseEnrollmentJson(await limitedBody(request, 16_384)), ["attempt_id", "credential"]);
    if ((await getConfig()).origin !== origin) throw new Error("ORIGIN_REJECTED");
    await finishPasskeyEnrollment(data.attempt_id, data.credential, authorized);
    if ((await getConfig()).origin !== origin) throw new Error("ORIGIN_REJECTED");
    const latest = await getSession();
    if (!latest) throw new Error("SESSION_REJECTED");
    assertAuthorizedSession(authorized, latest);
    return NextResponse.json({ registered: true }, { headers });
  } catch {
    return NextResponse.json({ error: "Registrierung nicht bestätigt. Status neu laden; ein verbrauchtes Ticket kann nicht erneut verwendet werden." }, { status: 400, headers });
  }
}
