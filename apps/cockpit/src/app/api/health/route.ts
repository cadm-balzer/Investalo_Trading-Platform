import { NextResponse } from "next/server";
export async function GET() {
  return NextResponse.json({ status: "ok", service: "cockpit", live_enabled: false }, { headers: { "Cache-Control": "no-store" } });
}
