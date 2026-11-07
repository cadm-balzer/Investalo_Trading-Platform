import { NextRequest, NextResponse } from "next/server";
import { finishLogin } from "@/lib/auth";
import { getConfig } from "@/lib/config";
import { COOKIE_OPTIONS, LOGIN_COOKIE, SESSION_COOKIE } from "@/lib/security";

export const dynamic = "force-dynamic";
export async function GET(request: NextRequest) {
  try {
    const config = await getConfig();
    const params = request.nextUrl.searchParams;
    if (params.getAll("state").length !== 1 || params.getAll("code").length !== 1 || params.has("error")) throw new Error("CALLBACK_REJECTED");
    const result = await finishLogin(params.get("state")!, params.get("code")!, request.cookies.get(LOGIN_COOKIE)?.value ?? "");
    const response = NextResponse.redirect(`${config.origin}/`);
    response.cookies.set(SESSION_COOKIE, result.id, { ...COOKIE_OPTIONS, maxAge: result.expiresAt - Math.floor(Date.now() / 1000) });
    response.cookies.set(LOGIN_COOKIE, "", { ...COOKIE_OPTIONS, maxAge: 0 });
    response.headers.set("Cache-Control", "no-store");
    return response;
  } catch {
    // No code, state, token, issuer details or user claims enter responses/logs.
    const response = NextResponse.json({ error: "Anmeldung nicht bestätigt. Bitte erneut anmelden." }, { status: 401, headers: { "Cache-Control": "no-store" } });
    response.cookies.set(LOGIN_COOKIE, "", { ...COOKIE_OPTIONS, maxAge: 0 });
    return response;
  }
}
