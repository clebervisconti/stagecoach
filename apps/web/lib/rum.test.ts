import assert from "node:assert/strict";
import { test } from "node:test";
import { redactExportedAttributes, rumInitOptions } from "./rum.ts";

const POISON_URL =
  "https://coach.example.test/sessions/poison-session-id/upload/poison-media-clip.mp4?email=person@example.test&q=poison-query#poison-transcript-body";
const POISON_TITLE = "poison-document-title";
const POISON_SESSION = "poison-session-id";
const POISON_MEDIA = "/data/stagecoach/poison-media-path/poison-media-clip.mp4";
const POISON_EMAIL = "person@example.test";
const POISON_TRANSCRIPT = "poison-transcript-body";

const POISONS = [
  POISON_URL,
  POISON_TITLE,
  POISON_SESSION,
  POISON_MEDIA,
  "poison-media-path",
  "poison-media-clip",
  POISON_EMAIL,
  "person%40example.test",
  POISON_TRANSCRIPT,
  "poison-query",
  "poison-fragment",
];

function poisonedAttributes(): Record<string, unknown> {
  return {
    app: "stagecoach",
    component: "document-load",
    "http.status_code": 200,
    "location.href": POISON_URL,
    "http.url": `fetch ${POISON_URL} failed`,
    "url.full": POISON_URL,
    "http.target": "/sessions/poison-session-id/upload/poison-media-clip.mp4?q=poison-query",
    "document.title": `${POISON_TITLE} rehearsal`,
    "splunk.rumSessionId": POISON_SESSION,
    "session.id": POISON_SESSION,
    "media.path": POISON_MEDIA,
    "transcript.text": `${POISON_TRANSCRIPT} from the rehearsal stand-in`,
    "error.message": `speaker ${POISON_EMAIL} opened ${POISON_URL}`,
    "enduser.id": "poison-user-id",
    "user.id": "poison-user-id",
    nested: {
      "document.title": POISON_TITLE,
      note: `encoded person%40example.test and ${POISON_TRANSCRIPT}`,
    },
  };
}

function exported(): Record<string, unknown> {
  return redactExportedAttributes(poisonedAttributes());
}

function dumped(attributes: Record<string, unknown>): string {
  return JSON.stringify(attributes);
}

test("strips query strings and fragments from exported URLs", () => {
  const attributes = exported();
  for (const key of ["location.href", "url.full", "http.target"]) {
    const value = String(attributes[key]);
    assert.equal(value.includes("?"), false, key);
    assert.equal(value.includes("#"), false, key);
  }
  assert.equal(String(attributes["location.href"]).startsWith("https://coach.example.test/"), true);
});

test("a poisoned full URL does not appear in exported attributes", () => {
  const dump = dumped(exported());
  assert.equal(dump.includes(POISON_URL), false);
  assert.equal(dump.includes("poison-query"), false);
  assert.equal(dump.includes("poison-transcript-body"), false);
});

test("a poisoned document title does not appear in exported attributes", () => {
  assert.equal(dumped(exported()).includes(POISON_TITLE), false);
});

test("a poisoned session id does not appear in exported attributes", () => {
  assert.equal(dumped(exported()).includes(POISON_SESSION), false);
});

test("a poisoned media path does not appear in exported attributes", () => {
  const dump = dumped(exported());
  assert.equal(dump.includes(POISON_MEDIA), false);
  assert.equal(dump.includes("poison-media-path"), false);
  assert.equal(dump.includes("poison-media-clip"), false);
});

test("email addresses are redacted from exported attributes", () => {
  const dump = dumped(exported());
  assert.equal(dump.includes(POISON_EMAIL), false);
  assert.equal(dump.includes("person%40example.test"), false);
  assert.equal(dump.includes("@"), false);
});

test("a poisoned transcript body does not appear in exported attributes", () => {
  assert.equal(dumped(exported()).includes(POISON_TRANSCRIPT), false);
});

test("exported attributes omit enduser.id and user.id", () => {
  const attributes = exported();
  assert.equal("enduser.id" in attributes, false);
  assert.equal("user.id" in attributes, false);
  assert.equal(dumped(attributes).includes("poison-user-id"), false);
  assert.equal(attributes.app, "stagecoach");
  assert.equal(attributes.component, "document-load");
  assert.equal(attributes["http.status_code"], 200);
});

test("the init exporter redacts attributes before they are serialized", () => {
  const options = rumInitOptions({ token: "example", doNotTrack: null, globalPrivacyControl: false });
  assert.ok(options);
  const serialized = options.exporter.onAttributesSerializing(poisonedAttributes());
  const dump = dumped(serialized);
  for (const poison of POISONS) {
    assert.equal(dump.includes(poison), false, poison);
  }
});

test("a missing token keeps RUM off", () => {
  assert.equal(rumInitOptions({ token: undefined }), null);
  assert.equal(rumInitOptions({ token: "" }), null);
  assert.equal(rumInitOptions({ token: "   " }), null);
});

test("Do Not Track skips initialization", () => {
  assert.equal(rumInitOptions({ token: "example", doNotTrack: "1" }), null);
  assert.equal(rumInitOptions({ token: "example", doNotTrack: "yes" }), null);
  assert.ok(rumInitOptions({ token: "example", doNotTrack: "0" }));
});

test("Global Privacy Control skips initialization", () => {
  assert.equal(rumInitOptions({ token: "example", globalPrivacyControl: true }), null);
  assert.ok(rumInitOptions({ token: "example", globalPrivacyControl: false }));
});

test("init matches the Stagecoach collector contract and leaves session replay unset", () => {
  const options = rumInitOptions({ token: "example" });
  assert.ok(options);
  assert.equal(options.realm, "us1");
  assert.equal(options.applicationName, "stagecoach");
  assert.equal(options.deploymentEnvironment, "production");
  assert.equal(options.beaconEndpoint, "https://rum-ingest.us1.signalfx.com/v1/rumotlp");
  assert.equal(options.persistence, "localStorage");
  assert.equal(options.user.trackingMode, "noTracking");
  assert.equal(options.privacy.maskAllText, true);
  assert.equal(options.exporter.otlp, true);
  assert.equal(Object.hasOwn(options, "sessionReplay"), false);
  assert.equal(Object.hasOwn(options, "cookieDomain"), false);
  assert.equal("enduser.id" in options, false);
  assert.equal("user.id" in options.user, false);
  const dumpedOptions = JSON.stringify(options);
  assert.equal(dumpedOptions.includes("form"), false);
});
