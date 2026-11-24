import { handleDemoControl } from "@/lib/demo-control-server";
export const dynamic = "force-dynamic";
export async function GET(request: Request) { return handleDemoControl(request); }
export async function POST(request: Request) { return handleDemoControl(request); }
