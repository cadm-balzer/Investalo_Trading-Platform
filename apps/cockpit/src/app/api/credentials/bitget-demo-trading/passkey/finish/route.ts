import { handleDemoTradingCredentialBrowserRequest } from "@/lib/demo-trading-passkey-credential-browser-server";

export async function POST(request: Request) {
  return handleDemoTradingCredentialBrowserRequest(request, "finish");
}
