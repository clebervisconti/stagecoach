/**
 * Splunk browser RUM for Stagecoach.
 * The npm package is bundled with the app. The committed token is empty.
 * Inject NEXT_PUBLIC_SPLUNK_RUM_TOKEN at image build time only after an
 * explicit deploy go. A missing token skips initialization.
 */

export const RUM_APPLICATION_NAME = "stagecoach";
export const RUM_REALM = "us1";
export const RUM_DEPLOYMENT_ENVIRONMENT = "production";
export const RUM_BEACON_ENDPOINT = "https://rum-ingest.us1.signalfx.com/v1/rumotlp";

const REPLACEMENT = "redacted";
const MEDIA_EXT = /\.(?:mp4|webm|mov|m4v|mkv|wav|mp3|m4a|aac|ogg|flac)$/i;
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/i;
const EMBEDDED_URL_SOURCE = "https?:\\/\\/[^\\s\"'<>]+";
const SENSITIVE_PARENTS = new Set([
  "sessions",
  "session",
  "upload",
  "derived",
  "media",
  "recordings",
]);
const SEGMENT_DENYLIST = new Set([
  "stagecoach",
  "sessions",
  "session",
  "upload",
  "derived",
  "media",
  "recordings",
  "data",
  "https",
  "http",
]);

export type RumInitOptions = {
  realm: typeof RUM_REALM;
  rumAccessToken: string;
  applicationName: typeof RUM_APPLICATION_NAME;
  deploymentEnvironment: typeof RUM_DEPLOYMENT_ENVIRONMENT;
  beaconEndpoint: typeof RUM_BEACON_ENDPOINT;
  persistence: "localStorage";
  user: { trackingMode: "noTracking" };
  privacy: { maskAllText: true };
  exporter: {
    otlp: true;
    onAttributesSerializing: (attributes: Record<string, unknown>) => Record<string, unknown>;
  };
};

export function rumInitOptions(input: {
  token: string | null | undefined;
  doNotTrack?: string | null;
  globalPrivacyControl?: boolean;
}): RumInitOptions | null {
  const token = input.token?.trim() ?? "";
  if (!token) return null;
  if (doNotTrackEnabled(input.doNotTrack)) return null;
  if (input.globalPrivacyControl === true) return null;

  return {
    realm: RUM_REALM,
    rumAccessToken: token,
    applicationName: RUM_APPLICATION_NAME,
    deploymentEnvironment: RUM_DEPLOYMENT_ENVIRONMENT,
    beaconEndpoint: RUM_BEACON_ENDPOINT,
    persistence: "localStorage",
    user: { trackingMode: "noTracking" },
    privacy: { maskAllText: true },
    exporter: {
      otlp: true,
      onAttributesSerializing: (attributes) => redactExportedAttributes(attributes),
    },
  };
}

export function readPrivacySignals(): {
  doNotTrack: string | null;
  globalPrivacyControl: boolean;
} {
  if (typeof navigator === "undefined") {
    return { doNotTrack: null, globalPrivacyControl: false };
  }
  const nav = navigator as Navigator & {
    globalPrivacyControl?: boolean;
    msDoNotTrack?: string;
  };
  const windowDnt =
    typeof window !== "undefined"
      ? (window as Window & { doNotTrack?: string }).doNotTrack
      : undefined;
  const dnt = nav.doNotTrack ?? nav.msDoNotTrack ?? windowDnt ?? null;
  return {
    doNotTrack: dnt == null ? null : String(dnt),
    globalPrivacyControl: nav.globalPrivacyControl === true,
  };
}

export function doNotTrackEnabled(value: string | null | undefined): boolean {
  if (value == null) return false;
  const normalized = value.trim().toLowerCase();
  return normalized === "1" || normalized === "yes";
}

/**
 * Last step before a span's attributes are serialized for export.
 * Query strings and fragments are stripped from URLs. Email addresses are
 * removed. Document title, session id, media path, transcript text, and the
 * original full URL are removed from every exported attribute.
 */
export function redactExportedAttributes(
  attributes: Record<string, unknown>,
): Record<string, unknown> {
  if (!isRecord(attributes)) return {};
  const literals = collectLiterals(attributes);
  const mapped = mapRecord(attributes);
  return scrubValue(mapped, literals) as Record<string, unknown>;
}

function collectLiterals(attributes: Record<string, unknown>): string[] {
  const found = new Set<string>();
  walk(attributes, null, (key, value) => {
    if (typeof value !== "string") return;
    if (key && (isWholeValueKey(key) || isUserIdKey(key))) {
      addLiteral(found, value);
      if (isMediaKey(key)) addMediaPieces(found, value);
    }
    for (const email of emailsIn(value)) addLiteral(found, email);
    if (key && isUrlKey(key)) addUrlPieces(found, value);
    for (const match of value.match(new RegExp(EMBEDDED_URL_SOURCE, "gi")) ?? []) addUrlPieces(found, match);
  });
  return [...found].sort((a, b) => b.length - a.length);
}

function addUrlPieces(found: Set<string>, raw: string): void {
  if (!looksLikeUrl(raw)) return;
  const sanitized = redactUrlish(raw);
  if (sanitized !== raw.trim()) addLiteral(found, raw);
  const parts = splitQueryAndFragment(raw);
  addLiteral(found, parts.search);
  addLiteral(found, parts.search.replace(/^[?]/, ""));
  addLiteral(found, parts.hash);
  addLiteral(found, parts.hash.replace(/^#/, ""));
  const basename = safeDecode(parts.path.split("/").pop() ?? "");
  if (MEDIA_EXT.test(basename)) addLiteral(found, basename);
}

function addMediaPieces(found: Set<string>, value: string): void {
  addLiteral(found, value);
  for (const segment of value.split(/[/?#\\]+/)) {
    const decoded = safeDecode(segment);
    if (decoded.length < 8) continue;
    if (SEGMENT_DENYLIST.has(decoded.toLowerCase())) continue;
    addLiteral(found, decoded);
  }
}

function splitQueryAndFragment(raw: string): { path: string; search: string; hash: string } {
  try {
    const url = new URL(raw, "https://stagecoach.invalid");
    const path = /^https?:\/\//i.test(raw) ? `${url.origin}${url.pathname}` : url.pathname;
    return { path, search: url.search, hash: url.hash };
  } catch {
    const hashAt = raw.indexOf("#");
    const queryAt = raw.indexOf("?");
    const hash = hashAt >= 0 ? raw.slice(hashAt) : "";
    const search = queryAt >= 0 ? raw.slice(queryAt, hashAt >= 0 ? hashAt : undefined) : "";
    const end = [hashAt, queryAt].filter((index) => index >= 0).sort((a, b) => a - b)[0];
    return { path: end === undefined ? raw : raw.slice(0, end), search, hash };
  }
}

function addLiteral(found: Set<string>, value: string): void {
  const trimmed = value.trim();
  if (trimmed.length < 4) return;
  if (trimmed.toLowerCase() === REPLACEMENT) return;
  found.add(trimmed);
}

function mapRecord(record: Record<string, unknown>): Record<string, unknown> {
  const next: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(record)) {
    if (isUserIdKey(key)) continue;
    next[key] = mapValue(key, value);
  }
  return next;
}

function mapValue(key: string | null, value: unknown): unknown {
  if (typeof value === "string") return redactString(key, value);
  if (Array.isArray(value)) return value.map((item) => mapValue(key, item));
  if (isRecord(value)) return mapRecord(value);
  return value;
}

function redactString(key: string | null, value: string): string {
  if (key && isWholeValueKey(key)) return REPLACEMENT;
  let next = key && isUrlKey(key) ? redactUrlish(value) : redactEmbeddedUrls(value);
  if (!(key && isUrlKey(key)) && next.startsWith("/")) next = redactUrlish(next);
  return redactEmails(next);
}

function redactEmbeddedUrls(value: string): string {
  return value.replace(new RegExp(EMBEDDED_URL_SOURCE, "gi"), (match) => redactAbsoluteUrl(match));
}

function redactUrlish(value: string): string {
  const trimmed = value.trim();
  if (trimmed.startsWith("?") || trimmed.startsWith("#")) return "";
  if (/^https?:\/\//i.test(trimmed)) return redactAbsoluteUrl(trimmed);
  const parts = splitQueryAndFragment(trimmed);
  return redactPath(parts.path);
}

function redactAbsoluteUrl(raw: string): string {
  try {
    const url = new URL(raw);
    url.search = "";
    url.hash = "";
    url.username = "";
    url.password = "";
    url.pathname = redactPath(url.pathname);
    return url.toString();
  } catch {
    return redactUrlish(raw.split(/[?#]/)[0] ?? raw);
  }
}

function redactPath(pathname: string): string {
  const segments = pathname.split("/");
  let previous = "";
  const next = segments.map((segment) => {
    const decoded = safeDecode(segment);
    const parent = previous.toLowerCase();
    previous = decoded;
    if (!decoded) return segment;
    if (SENSITIVE_PARENTS.has(parent) || UUID.test(decoded) || MEDIA_EXT.test(decoded) || EMAIL.test(decoded)) {
      return REPLACEMENT;
    }
    return segment;
  });
  return next.join("/");
}

function redactEmails(value: string): string {
  return value
    .replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/gi, REPLACEMENT)
    .replace(/[A-Za-z0-9._%+-]+%40[A-Za-z0-9.-]+(?:%2E|\.)[A-Za-z]{2,}/gi, REPLACEMENT);
}

function emailsIn(value: string): string[] {
  const found = new Set<string>();
  const pattern = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/gi;
  for (const match of value.match(pattern) ?? []) found.add(match);
  const decoded = safeDecode(value);
  if (decoded !== value) {
    for (const match of decoded.match(pattern) ?? []) found.add(match);
  }
  return [...found];
}

function scrubValue(value: unknown, literals: string[]): unknown {
  if (typeof value === "string") {
    let next = value;
    for (const literal of literals) {
      if (!literal || !next.includes(literal)) continue;
      next = next.split(literal).join(REPLACEMENT);
    }
    return next;
  }
  if (Array.isArray(value)) return value.map((item) => scrubValue(item, literals));
  if (isRecord(value)) {
    const next: Record<string, unknown> = {};
    for (const [key, child] of Object.entries(value)) next[key] = scrubValue(child, literals);
    return next;
  }
  return value;
}

function walk(
  value: unknown,
  key: string | null,
  visit: (key: string | null, value: unknown) => void,
): void {
  visit(key, value);
  if (Array.isArray(value)) {
    for (const item of value) walk(item, key, visit);
  } else if (isRecord(value)) {
    for (const [childKey, child] of Object.entries(value)) walk(child, childKey, visit);
  }
}

function looksLikeUrl(value: string): boolean {
  return /^https?:\/\//i.test(value) || value.startsWith("/") || value.startsWith("?") || value.startsWith("#");
}

function isWholeValueKey(key: string): boolean {
  return isTitleKey(key) || isSessionKey(key) || isMediaKey(key) || isTranscriptKey(key);
}

function isTitleKey(key: string): boolean {
  const normalized = key.toLowerCase();
  return (
    normalized === "document.title" ||
    normalized === "page.title" ||
    normalized === "doc.title" ||
    normalized.endsWith(".document.title")
  );
}

function isSessionKey(key: string): boolean {
  const normalized = key.toLowerCase();
  return (
    normalized === "splunk.rumsessionid" ||
    normalized === "session.id" ||
    normalized === "rum.session.id" ||
    normalized === "sessionid" ||
    normalized.endsWith(".session.id") ||
    normalized.endsWith("rumsessionid")
  );
}

function isUserIdKey(key: string): boolean {
  const normalized = key.toLowerCase();
  return (
    normalized === "enduser.id" ||
    normalized === "user.id" ||
    normalized === "enduser.pseudoid" ||
    normalized.endsWith(".user.id")
  );
}

function isMediaKey(key: string): boolean {
  return /media[._-]?path|media[._-]?uri|storage[._-]?uri|recording[._-]?(path|uri|url)|file[._-]?path/i.test(
    key,
  );
}

function isTranscriptKey(key: string): boolean {
  return /transcript|coaching|utterance|caption/i.test(key);
}

function isUrlKey(key: string): boolean {
  const normalized = key.toLowerCase();
  return (
    normalized === "location.href" ||
    normalized === "http.url" ||
    normalized === "url.full" ||
    normalized === "http.target" ||
    normalized === "page.url" ||
    normalized === "document.url" ||
    normalized === "document.referrer" ||
    normalized === "location.search" ||
    normalized === "location.hash" ||
    normalized === "url" ||
    normalized === "href" ||
    normalized.endsWith(".href") ||
    normalized.endsWith(".url")
  );
}

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
