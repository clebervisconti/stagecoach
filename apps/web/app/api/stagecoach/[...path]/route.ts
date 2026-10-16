import { stagecoachApi } from "@/lib/api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const SAFE_SEGMENT = /^[A-Za-z0-9._-]+$/;
const ALLOWED_METHODS = new Set(["GET", "POST", "PATCH", "DELETE"]);

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
  let parts: string[];
  try {
    parts = (await params).path;
    path = apiPath(parts);
  } catch {
    return Response.json({ detail: "Invalid path" }, { status: 400 });
  }

  const incoming = new URL(request.url);
  const forwarded = new URLSearchParams();
  const exp = incoming.searchParams.get("exp");
  const sig = incoming.searchParams.get("sig");
  const locale = incoming.searchParams.get("locale");
  const t = incoming.searchParams.get("t");
  const i = incoming.searchParams.get("i");
  if (exp && /^\d+$/.test(exp)) forwarded.set("exp", exp);
  if (sig && /^[a-fA-F0-9]+$/.test(sig)) forwarded.set("sig", sig);
  if (locale === "en" || locale === "pt-BR") forwarded.set("locale", locale);
  if (t && /^\d+(\.\d+)?$/.test(t)) forwarded.set("t", t);
  if (i && /^\d+$/.test(i)) forwarded.set("i", i);
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
  if (request.method === "POST" || request.method === "PATCH") {
    init.body = request.body;
    init.duplex = "half";
  }

  const upstream = await stagecoachApi(path, init, { anonymous: parts[0] === "auth" });
  const responseHeaders = new Headers();
  for (const name of [
    "content-type",
    "content-length",
    "content-disposition",
    "accept-ranges",
    "content-range",
    "x-accel-buffering",
    "connection",
  ]) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  responseHeaders.set("cache-control", "no-store");
  if ((upstream.headers.get("content-type") || "").includes("text/event-stream")) {
    responseHeaders.set("cache-control", "no-cache");
    responseHeaders.set("connection", "keep-alive");
    responseHeaders.set("x-accel-buffering", "no");
  }
  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
