export function mutationAllowed(input: {
  method: string;
  origin: string | null;
  host: string | null;
  forwardedHost: string | null;
  secFetchSite: string | null;
}): boolean {
  const method = input.method.toUpperCase();
  if (method === "GET" || method === "HEAD" || method === "OPTIONS") return true;
  if ((input.secFetchSite || "").toLowerCase() === "cross-site") return false;
  const originHost = hostOf(input.origin);
  if (!originHost) return false;
  const expected = [input.forwardedHost, input.host]
    .flatMap((value) => (value || "").split(","))
    .map((value) => hostOf(value))
    .filter((value): value is string => Boolean(value));
  return expected.includes(originHost);
}

function hostOf(value: string | null): string | null {
  const trimmed = (value || "").trim();
  if (!trimmed) return null;
  try {
    const withScheme = trimmed.includes("://") ? trimmed : `http://${trimmed}`;
    return new URL(withScheme).host.toLowerCase();
  } catch {
    return null;
  }
}
