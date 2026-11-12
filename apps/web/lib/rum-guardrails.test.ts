import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { privacyPolicy } from "./privacy-policy.ts";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "../../..");
const webRoot = join(here, "..");

const SKIP_DIRS = new Set([
  ".git",
  "node_modules",
  ".next",
  "dist",
  "coverage",
  ".turbo",
]);

function filesUnder(dir: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIRS.has(entry)) continue;
    const path = join(dir, entry);
    const stat = statSync(path);
    if (stat.isDirectory()) {
      found.push(...filesUnder(path));
      continue;
    }
    found.push(path);
  }
  return found;
}

function textFiles(): string[] {
  return filesUnder(repoRoot).filter((path) =>
    /\.(ts|tsx|js|mjs|json|yml|yaml|md|sh|example|Dockerfile)$/.test(path) ||
    path.endsWith("Dockerfile"),
  );
}

test("session replay is not enabled or depended on", () => {
  const packageJson = JSON.parse(readFileSync(join(webRoot, "package.json"), "utf8")) as {
    dependencies?: Record<string, string>;
    devDependencies?: Record<string, string>;
  };
  const deps = { ...packageJson.dependencies, ...packageJson.devDependencies };
  assert.equal(deps["@splunk/otel-web"], "3.2.0");
  const replayPackage = ["@splunk/otel-web", "session-replay"].join("-");
  const recorderPackage = ["@splunk/", "otel-web-session-recorder"].join("");
  for (const name of Object.keys(deps)) {
    assert.equal(name === replayPackage, false, name);
    assert.equal(name.includes("session-replay"), false, name);
    assert.equal(name.includes("session-recorder"), false, name);
  }

  const sessionReplayAssignment = ["session", "Replay:"].join("");
  const recorderSymbol = ["Splunk", "Session", "Recorder"].join("");
  for (const path of textFiles()) {
    const text = readFileSync(path, "utf8");
    const rel = relative(repoRoot, path);
    assert.equal(text.includes(replayPackage), false, rel);
    assert.equal(text.includes(recorderPackage), false, rel);
    assert.equal(text.includes(recorderSymbol), false, rel);
    assert.equal(text.includes(sessionReplayAssignment), false, rel);
  }
});

test("a non-empty RUM token is not committed", () => {
  const assignment =
    /(?:NEXT_PUBLIC_SPLUNK_RUM_TOKEN|SPLUNK_RUM_TOKEN)[ \t]*[:=][ \t]*([^\s#]+)/g;
  const literalToken = /rumAccessToken\s*:\s*(["'])([^"']*)\1/g;
  for (const path of textFiles()) {
    const text = readFileSync(path, "utf8");
    const rel = relative(repoRoot, path);
    for (const match of text.matchAll(assignment)) {
      assert.equal(isCommittedToken(match[1] ?? ""), false, `${rel}: ${match[0]}`);
    }
    for (const match of text.matchAll(literalToken)) {
      assert.equal((match[2] ?? "").trim() === "", true, `${rel}: rumAccessToken literal`);
    }
  }
});

function isCommittedToken(raw: string): boolean {
  const value = raw.trim().replace(/^["']|["']$/g, "");
  if (!value) return false;
  if (value.startsWith("$")) return false;
  if (value.includes("security")) return false;
  return true;
}

test("the public privacy policy states the RUM limits in both languages", () => {
  const en = privacyPolicy("en").paragraphs.join("\n");
  assert.match(en, /Splunk Real User Monitoring \(RUM\)/);
  assert.match(en, /session id is stored in localStorage/);
  assert.match(en, /no Splunk cookie/);
  assert.match(en, /no anonymous user id/);
  assert.match(en, /country code/);
  assert.match(en, /raw IP is not kept/);
  assert.match(en, /Session replay is off and is not loaded/);
  assert.match(en, /Forms and user IDs are not captured/);
  assert.match(en, /transcript/);
  assert.match(en, /media path/);
  assert.match(en, /raw URL/);
  assert.match(en, /does not ask for an acceptance click/);

  const pt = privacyPolicy("pt-BR").paragraphs.join("\n");
  assert.match(pt, /Splunk Real User Monitoring \(RUM\)/);
  assert.match(pt, /localStorage/);
  assert.match(pt, /cookie do Splunk/);
  assert.match(pt, /identificador anônimo de usuário/);
  assert.match(pt, /código de país/);
  assert.match(pt, /IP bruto não é mantido/);
  assert.match(pt, /reprodução de sessão está desligada e não é carregada/);
  assert.match(pt, /Formulários e identificadores de usuário não são capturados/);
  assert.match(pt, /transcrição/);
  assert.match(pt, /caminho da mídia/);
  assert.match(pt, /URL bruta/);
  assert.match(pt, /não pede um clique de aceite/);

  const page = readFileSync(join(webRoot, "app/[locale]/privacy/page.tsx"), "utf8");
  assert.equal(page.includes("checkbox"), false);
  assert.equal(page.includes("Aceitar"), false);
  assert.equal(page.includes("I agree"), false);

  const policy = readFileSync(join(repoRoot, "docs/PRIVACY.md"), "utf8");
  assert.match(policy, /Splunk Real User Monitoring/);
  assert.match(policy, /localStorage/);
  assert.match(policy, /no Splunk cookie/);
  assert.match(policy, /no anonymous user id/);
  assert.match(policy, /country code/);
  assert.match(policy, /raw IP is not kept/);
  assert.match(policy, /Session replay is off/);
  assert.match(policy, /not loaded/);
  assert.match(policy, /Forms and user IDs are not captured/);
  assert.match(policy, /transcript/);
  assert.match(policy, /media path/);
  assert.match(policy, /raw URL/);
  assert.match(policy, /acceptance click/);
});
