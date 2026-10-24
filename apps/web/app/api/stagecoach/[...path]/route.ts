import { stagecoachApi } from "@/lib/api";
import { mutationAllowed } from "@/lib/csrf";
import { upstreamResponseHeaders } from "@/lib/upstream-headers";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const SAFE_SEGMENT = /^[A-Za-z0-9._-]+$/;
const ALLOWED_METHODS = new Set(["GET", "POST", "PUT", "PATCH", "DELETE"]);
const ANONYMOUS_AUTH = new Set(["login", "register", "forgot", "verify-email", "reset", "session-ticket"]);

function isAnonymous(parts: string[]): boolean {
  if (parts[0] !== "auth") return false;
  if (parts[1] === "apple") return true;
  return ANONYMOUS_AUTH.has(parts[1] ?? "");
}

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
  if (
    !mutationAllowed({
      method: request.method,
      origin: request.headers.get("origin"),
      host: request.headers.get("host"),
      forwardedHost: request.headers.get("x-forwarded-host"),
      secFetchSite: request.headers.get("sec-fetch-site"),
    })
  ) {
    return Response.json({ detail: "Cross-site request blocked" }, { status: 403 });
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
  const purpose = incoming.searchParams.get("purpose");
  const asset = incoming.searchParams.get("asset");
  if (exp && /^\d+$/.test(exp)) forwarded.set("exp", exp);
  if (sig && /^[a-fA-F0-9]+$/.test(sig)) forwarded.set("sig", sig);
  if (locale === "en" || locale === "pt-BR") forwarded.set("locale", locale);
  if (t && /^\d+(\.\d+)?$/.test(t)) forwarded.set("t", t);
  if (i && /^\d+$/.test(i)) forwarded.set("i", i);
  if (purpose === "export") forwarded.set("purpose", "export");
  if (asset && SAFE_SEGMENT.test(asset)) forwarded.set("asset", asset);
  const query = forwarded.toString();
  if (query) path = `${path}?${query}`;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const contentLength = request.headers.get("content-length");
  const range = request.headers.get("range");
  if (contentType) headers.set("content-type", contentType);
  if (contentLength) headers.set("content-length", contentLength);
  if (range) headers.set("range", range);
  const forwardedFor = request.headers.get("x-forwarded-for");
  const realIp = request.headers.get("x-real-ip");
  if (forwardedFor) headers.set("x-forwarded-for", forwardedFor);
  else if (realIp) headers.set("x-forwarded-for", realIp);

  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers,
  };
  if (request.method === "POST" || request.method === "PUT" || request.method === "PATCH") {
    init.body = request.body;
    init.duplex = "half";
  }

  const upstream = await stagecoachApi(path, init, { anonymous: isAnonymous(parts) });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: upstreamResponseHeaders(upstream.headers),
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
