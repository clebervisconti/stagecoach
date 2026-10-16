"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { planToMarkdown, type PlanRecord } from "@/lib/plan-export";

export default function PlanPrintPage() {
  const t = useTranslations("planEditor");
  const params = useParams<{ id: string }>();
  const [markdown, setMarkdown] = useState("");

  useEffect(() => {
    void fetch(`/api/stagecoach/plans/${params.id}`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return;
        const plan = (await response.json()) as PlanRecord;
        setMarkdown(planToMarkdown(plan));
      });
  }, [params.id]);

  return (
    <div className="mx-auto max-w-3xl px-6 py-8" data-testid="plan-print">
      <div className="mb-4 print:hidden">
        <button
          type="button"
          data-testid="print-plan"
          onClick={() => window.print()}
          className="rounded-md bg-primary px-3 py-1 text-sm text-primary-foreground"
        >
          {t("exportPdf")}
        </button>
      </div>
      <pre className="whitespace-pre-wrap text-sm">{markdown}</pre>
    </div>
  );
}
