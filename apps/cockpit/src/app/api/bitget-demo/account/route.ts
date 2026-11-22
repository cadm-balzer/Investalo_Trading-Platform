import { handleDemoAccount } from "@/lib/demo-account-server";
export const dynamic = "force-dynamic";
export async function GET(request: Request) { return handleDemoAccount(request); }
