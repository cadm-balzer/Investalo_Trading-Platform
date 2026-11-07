import { NextRequest, NextResponse } from "next/server";
import { destroySession, getSession } from "@/lib/auth";
import { getConfig } from "@/lib/config";
import { COOKIE_OPTIONS, SESSION_COOKIE, limitedBody, requireCsrf, requireSameOrigin } from "@/lib/security";

export async function POST(request: NextRequest) {
  try {
    const config = await getConfig();
    requireSameOrigin(request, config.origin);
    const session = await getSession();
    if (!session) return NextResponse.json({ error: "Nicht angemeldet." }, { status: 401 });
    if (request.headers.get("content-type")?.split(";")[0] !== "application/x-www-form-urlencoded") throw new Error("BODY_REJECTED");
    const form = new URLSearchParams(await limitedBody(request));
    if (form.getAll("csrf").length !== 1) throw new Error("CSRF_REJECTED");
    requireCsrf(session.csrf, form.get("csrf"));
    await destroySession();
    const response = NextResponse.redirect(`${config.origin}/`, 303);
    response.cookies.set(SESSION_COOKIE, "", { ...COOKIE_OPTIONS, maxAge: 0 });
    response.headers.set("Cache-Control", "no-store");
    return response;
  } catch { return NextResponse.json({ error: "Abmeldung abgelehnt." }, { status: 403 }); }
}
