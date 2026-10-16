import { expect, test } from "@playwright/test";
import { mockStagecoachApi } from "./helpers.ts";

test("settings export download and 7-day deletion request", async ({ page }) => {
  await mockStagecoachApi(page, { language: "en", title: "Export talk" });
  await page.goto("/settings", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("account-rights-panel")).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByTestId("export-data").click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/stagecoach-export/);
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("delete-account").click();
  await expect(page.getByTestId("deletion-pending")).toBeVisible();
  await expect(page.getByTestId("cancel-deletion")).toBeVisible();
});
