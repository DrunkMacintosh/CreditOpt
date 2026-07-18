import { proxyCreditOpsRequest } from "../../../../lib/server/creditops-bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

async function forward(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  return proxyCreditOpsRequest(request, path);
}

export { forward as GET, forward as POST };
