"use client";

import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { CONTEXT_TYPES, buildPlanPayload } from "@/lib/prep-form";

type ClarifyResponse = {
  questions: { id: string; prompt: string }[];
  assumptions: string[];
  skipped: boolean;
};

export function PlanForm() {
  const t = useTranslations("planForm");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [clarify, setClarify] = useState<ClarifyResponse | null>(null);
  const [planId, setPlanId] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const created = await fetch("/api/stagecoach/plans", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(buildPlanPayload(form)),
      });
      const body = await created.json();
      if (!created.ok) throw new Error(body.detail || t("createError"));
      setPlanId(body.id);
      const clarified = await fetch(`/api/stagecoach/plans/${body.id}/clarify`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ description: form.get("description") }),
      });
      const result = await clarified.json();
      if (!clarified.ok) throw new Error(result.detail || t("clarifyError"));
      setClarify(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("createError"));
    } finally {
      setSubmitting(false);
    }
  }

  async function skipQuestions() {
    if (!planId) return;
    setSubmitting(true);
    try {
      const response = await fetch(`/api/stagecoach/plans/${planId}/clarify`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ skip: true }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || t("clarifyError"));
      setClarify(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("clarifyError"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <form data-testid="plan-form" onSubmit={submit} className="space-y-4">
        <label className="block text-sm font-medium">
          {t("title")}
          <input name="title" required maxLength={255} className="mt-1 w-full rounded-md border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">
          {t("context")}
          <select name="context_type" defaultValue="exec_briefing" className="mt-1 w-full rounded-md border px-3 py-2">
            {CONTEXT_TYPES.map((value) => (
              <option key={value} value={value}>
                {t(`contexts.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm font-medium">
          {t("description")}
          <textarea
            name="description"
            required
            maxLength={4000}
            rows={6}
            className="mt-1 w-full rounded-md border px-3 py-2"
            data-testid="plan-description"
          />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm font-medium">
            {t("roles")}
            <input name="audience_roles" className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
          <label className="block text-sm font-medium">
            {t("seniority")}
            <input name="audience_seniority" className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
          <label className="block text-sm font-medium">
            {t("depth")}
            <input name="audience_depth" type="number" min={1} max={5} className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
          <label className="block text-sm font-medium">
            {t("size")}
            <input name="audience_size" className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
          <label className="block text-sm font-medium">
            {t("audienceLanguage")}
            <input name="audience_language" className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
          <label className="block text-sm font-medium">
            {t("decision")}
            <input name="audience_decision" className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
        </div>
        <label className="block text-sm font-medium">
          {t("know")}
          <textarea name="audience_know" rows={2} className="mt-1 w-full rounded-md border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">
          {t("care")}
          <textarea name="audience_care" rows={2} className="mt-1 w-full rounded-md border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">
          {t("objections")}
          <textarea name="audience_objections" rows={2} className="mt-1 w-full rounded-md border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">
          {t("goal")}
          <input name="goal" className="mt-1 w-full rounded-md border px-3 py-2" />
        </label>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="block text-sm font-medium">
            {t("slot")}
            <input name="slot_min" type="number" min={1} max={180} className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
          <label className="flex items-center gap-2 text-sm font-medium">
            <input name="qa_in_slot" type="checkbox" />
            {t("qaInSlot")}
          </label>
          <label className="block text-sm font-medium">
            {t("qaMin")}
            <input name="qa_min" type="number" min={0} max={120} className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
        </div>
        <label className="flex items-center gap-2 text-sm font-medium">
          <input name="late_start" type="checkbox" />
          {t("lateStart")}
        </label>
        <label className="block text-sm font-medium">
          {t("format")}
          <select name="delivery_format" className="mt-1 w-full rounded-md border px-3 py-2">
            <option value="">{t("formatUnset")}</option>
            <option value="in_person">{t("inPerson")}</option>
            <option value="virtual">{t("virtual")}</option>
            <option value="hybrid">{t("hybrid")}</option>
          </select>
        </label>
        <label className="block text-sm font-medium">
          {t("language")}
          <select name="language" defaultValue="en" className="mt-1 w-full rounded-md border px-3 py-2">
            <option value="en">English</option>
            <option value="pt-BR">Português</option>
          </select>
        </label>
        <label className="block text-sm font-medium">
          {t("habits")}
          <input name="known_habits" className="mt-1 w-full rounded-md border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">
          {t("mustInclude")}
          <textarea name="must_include" rows={2} className="mt-1 w-full rounded-md border px-3 py-2" />
        </label>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <button
          type="submit"
          data-testid="plan-submit"
          disabled={submitting}
          className="rounded-md bg-primary px-4 py-2 text-primary-foreground"
        >
          {submitting ? t("saving") : t("submit")}
        </button>
      </form>

      {clarify && clarify.questions.length > 0 ? (
        <div data-testid="clarify-questions" className="rounded-lg border p-4">
          <h2 className="mb-2 font-semibold">{t("questionsHeading")}</h2>
          <ol className="list-decimal space-y-1 pl-5 text-sm">
            {clarify.questions.map((question) => (
              <li key={question.id}>{question.prompt}</li>
            ))}
          </ol>
          <button
            type="button"
            data-testid="skip-clarify"
            onClick={() => void skipQuestions()}
            className="mt-3 rounded-md border px-3 py-1 text-sm"
          >
            {t("skip")}
          </button>
        </div>
      ) : null}

      {clarify && clarify.assumptions.length > 0 ? (
        <div data-testid="clarify-assumptions" className="rounded-lg border p-4">
          <h2 className="mb-2 font-semibold">{t("assumptionsHeading")}</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {clarify.assumptions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
