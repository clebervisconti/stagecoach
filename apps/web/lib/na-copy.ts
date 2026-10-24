import { isNaCode } from "./online.ts";

export function isLanguageModelGap(reason: string | null | undefined, code?: string | null): boolean {
  if (code === "model_unavailable") return true;
  return /language model|modelo de linguagem/i.test(reason || "");
}

export function isCameraCoverageGap(reason: string | null | undefined, code?: string | null): boolean {
  if (code === "camera_coverage_low") return true;
  return /fills the frame|preenche o quadro|camera coverage/i.test(reason || "");
}

type NaCategory = {
  id?: string;
  na_code?: string | null;
  na_reason?: string | null;
};

/** Prefer the real cause over the generic "not measured" line. */
export function categoryNaCopy(category: NaCategory, t: (key: string) => string): string {
  const reason = (category.na_reason || "").trim();
  if (isLanguageModelGap(reason, category.na_code)) return t("na.model_unavailable");
  if (isCameraCoverageGap(reason, category.na_code)) return t("na.camera_coverage_low");
  if (category.id === "screen_flow" && !reason && !isNaCode(category.na_code)) return t("na.screenFlowSoon");
  if (isNaCode(category.na_code) && category.na_code !== "not_applicable") return t(`na.${category.na_code}`);
  if (reason) return reason;
  if (isNaCode(category.na_code)) return t(`na.${category.na_code}`);
  return t("na.not_applicable");
}
