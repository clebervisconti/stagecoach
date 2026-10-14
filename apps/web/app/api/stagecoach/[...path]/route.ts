import { stagecoachApi } from "@/lib/api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const SAFE_SEGMENT = /^[A-Za-z0-9_-]+$/;
const ALLOWED_METHODS = new Set(["GET", "POST", "DELETE"]);

function apiPath(parts: string[]): string {
  if (!parts.length || parts.some((part) => !SAFE_SEGMENT.test(part))) {
    throw new Error("Invalid API path");
  }
  return `/api/v1/${parts.map(encodeURIComponent).join("/")}`;
}

async function proxy(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  if (!ALLOWED_METHODS.has(request.method)) {
    return Response.json({ detail: "Method not allowed" }, { status: 405 });
  }

  let path: string;
  try {
    path = apiPath((await params).path);
  } catch {
    return Response.json({ detail: "Invalid path" }, { status: 400 });
  }

  const incoming = new URL(request.url);
  const forwarded = new URLSearchParams();
  const exp = incoming.searchParams.get("exp");
  const sig = incoming.searchParams.get("sig");
  if (exp && /^\d+$/.test(exp)) forwarded.set("exp", exp);
  if (sig && /^[a-fA-F0-9]+$/.test(sig)) forwarded.set("sig", sig);
  const query = forwarded.toString();
  if (query) path = `${path}?${query}`;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const contentLength = request.headers.get("content-length");
  const range = request.headers.get("range");
  if (contentType) headers.set("content-type", contentType);
  if (contentLength) headers.set("content-length", contentLength);
  if (range) headers.set("range", range);

  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers,
  };
  if (request.method === "POST") {
    init.body = request.body;
    init.duplex = "half";
  }

  const upstream = await stagecoachApi(path, init);
  const responseHeaders = new Headers();
  for (const name of [
    "content-type",
    "content-length",
    "content-disposition",
    "accept-ranges",
    "content-range",
  ]) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  responseHeaders.set("cache-control", "no-store");
  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const DELETE = proxy;
