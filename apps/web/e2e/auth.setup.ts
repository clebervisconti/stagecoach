import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { test as setup } from "@playwright/test";
import { sessionCookie } from "./session-cookie.ts";

const authFile = "e2e/.auth/member.json";

setup("write member session", async () => {
  const cookie = await sessionCookie({
    id: "11111111-1111-4111-8111-111111111101",
    email: "ci@example.invalid",
    role: "member",
    mustChangePassword: false,
    sessionVersion: 1,
  });
  mkdirSync(dirname(authFile), { recursive: true });
  writeFileSync(authFile, JSON.stringify({ cookies: [cookie], origins: [] }));
});
