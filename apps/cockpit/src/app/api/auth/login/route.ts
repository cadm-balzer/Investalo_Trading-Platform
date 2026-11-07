import { NextResponse } from "next/server";
import { beginLogin } from "@/lib/auth";
import { COOKIE_OPTIONS, LOGIN_COOKIE } from "@/lib/security";

export const dynamic = "force-dynamic";
export async function GET() {
  try {
    const login = await beginLogin();
    const response = NextResponse.redirect(login.authorizationUrl);
    response.cookies.set(LOGIN_COOKIE, login.binding, { ...COOKIE_OPTIONS, maxAge: 300 });
    response.headers.set("Cache-Control", "no-store");
    return response;
  } catch {
    return NextResponse.json({ error: "Die sichere Anmeldung ist noch nicht verfügbar." }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}
