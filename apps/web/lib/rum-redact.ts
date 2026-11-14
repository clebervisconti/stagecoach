/**
 * Redact browser RUM attributes before export.
 * Session and prep identifiers, and query strings, do not leave the browser.
 * The replacement token matches the Stage Coach redaction contract.
 */

const REPLACEMENT = "redacted";
const SENSITIVE_PARENTS = new Set(["sessions", "session", "prep", "upload", "derived", "media", "recordings"]);
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isUrlKey(key: string): boolean {
  const normalized = key.toLowerCase();
  return (
    normalized === "location.href" ||
    normalized === "http.url" ||
    normalized === "url.full" ||
    normalized === "http.target" ||
    normalized === "page.url" ||
    normalized === "document.url" ||
    normalized === "url" ||
    normalized === "href" ||
    normalized.endsWith(".href") ||
    normalized.endsWith(".url")
  );
}

function redactPath(pathname: string, literals: Set<string>): string {
  const segments = pathname.split("/");
  let previous = "";
  return segments
    .map((segment) => {
      let decoded = segment;
      try {
        decoded = decodeURIComponent(segment);
      } catch {
        decoded = segment;
      }
      const parent = previous.toLowerCase();
      previous = decoded;
      if (!decoded) return segment;
      if (SENSITIVE_PARENTS.has(parent) || UUID.test(decoded)) {
        if (decoded.length >= 4) literals.add(decoded);
        return REPLACEMENT;
      }
      return segment;
    })
    .join("/");
}

export function redactUrl(value: string, literals: Set<string>): string {
  const trimmed = value.trim();
  if (!trimmed) return trimmed;
  try {
    const absolute = /^https?:\/\//i.test(trimmed);
    const url = new URL(trimmed, "https://stagecoach.invalid");
    if (url.search) literals.add(url.search);
    if (url.search.length > 1) literals.add(url.search.slice(1));
    if (url.hash) literals.add(url.hash);
    url.search = "";
    url.hash = "";
    url.username = "";
    url.password = "";
    url.pathname = redactPath(url.pathname, literals);
    if (absolute) return url.toString();
    return `${url.pathname}${url.search}`;
  } catch {
    const cut = trimmed.split(/[?#]/)[0] ?? trimmed;
    return redactPath(cut, literals);
  }
}

function mapValue(key: string | null, value: unknown, literals: Set<string>): unknown {
  if (typeof value === "string") {
    if (key && isUrlKey(key)) return redactUrl(value, literals);
    if (value.startsWith("/") || /^https?:\/\//i.test(value)) return redactUrl(value, literals);
    return value;
  }
  if (Array.isArray(value)) return value.map((item) => mapValue(key, item, literals));
  if (value && typeof value === "object") return mapRecord(value as Record<string, unknown>, literals);
  return value;
}

function mapRecord(record: Record<string, unknown>, literals: Set<string>): Record<string, unknown> {
  const next: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(record)) next[key] = mapValue(key, value, literals);
  return next;
}

function scrub(value: unknown, literals: string[]): unknown {
  if (typeof value === "string") {
    let next = value;
    for (const literal of literals) {
      if (literal && next.includes(literal)) next = next.split(literal).join(REPLACEMENT);
    }
    return next;
  }
  if (Array.isArray(value)) return value.map((item) => scrub(item, literals));
  if (value && typeof value === "object") {
    const next: Record<string, unknown> = {};
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) next[key] = scrub(child, literals);
    return next;
  }
  return value;
}

export function redactRumAttributes(attributes: Record<string, unknown>): Record<string, unknown> {
  const literals = new Set<string>();
  const mapped = mapRecord(attributes, literals);
  const ordered = [...literals].filter((item) => item.length >= 4).sort((a, b) => b.length - a.length);
  return scrub(mapped, ordered) as Record<string, unknown>;
}
