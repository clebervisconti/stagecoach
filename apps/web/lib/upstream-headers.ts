/** Response headers the BFF copies from the API. Retry-After has to survive a 429. */

export const FORWARDED_UPSTREAM_HEADERS = [
  "content-type",
  "content-length",
  "content-disposition",
  "accept-ranges",
  "content-range",
  "x-accel-buffering",
  "connection",
  "retry-after",
] as const;

export function upstreamResponseHeaders(upstream: Headers): Headers {
  const responseHeaders = new Headers();
  for (const name of FORWARDED_UPSTREAM_HEADERS) {
    const value = upstream.get(name);
    if (value) responseHeaders.set(name, value);
  }
  responseHeaders.set("cache-control", "no-store");
  if ((upstream.get("content-type") || "").includes("text/event-stream")) {
    responseHeaders.set("cache-control", "no-cache");
    responseHeaders.set("connection", "keep-alive");
    responseHeaders.set("x-accel-buffering", "no");
  }
  return responseHeaders;
}
