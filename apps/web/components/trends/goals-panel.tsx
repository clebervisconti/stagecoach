"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useLocale } from "next-intl";

type GoalRow = {
  id?: string;
  metric_id?: string | null;
  category_id?: string | null;
  comparator: string;
  target: number;
  latest_value?: number | null;
  achieved_at?: string | null;
  label?: string;
};

const COPY = {
  en: {
    heading: "Goals",
    intro: "Set a metric or category target (for example filler sounds < 3/min). Progress uses the latest session.",
    kind: "Target kind",
    metric: "Metric",
    category: "Category",
    comparator: "Comparator",
    target: "Target",
    add: "Add goal",
    empty: "No goals yet.",
    createError: "Could not create the goal.",
    loadError: "Could not load goals.",
    achieved: "achieved",
  },
  "pt-BR": {
    heading: "Metas",
    intro: "Defina uma meta de métrica ou categoria (por exemplo fillers < 3/min). O progresso usa a sessão mais recente.",
    kind: "Tipo de alvo",
    metric: "Métrica",
    category: "Categoria",
    comparator: "Comparador",
    target: "Alvo",
    add: "Adicionar meta",
    empty: "Ainda não há metas.",
    createError: "Não foi possível criar a meta.",
    loadError: "Não foi possível carregar as metas.",
    achieved: "alcançada",
  },
} as const;

export function GoalsPanel() {
  const locale = useLocale();
  const t = COPY[locale === "pt-BR" ? "pt-BR" : "en"];
  const [goals, setGoals] = useState<GoalRow[]>([]);
  const [error, setError] = useState("");
  const [kind, setKind] = useState<"metric" | "category">("metric");
  const [busy, setBusy] = useState(false);

  async function load() {
    const response = await fetch("/api/stagecoach/goals", { cache: "no-store" });
    const body = (await response.json()) as { goals?: GoalRow[]; detail?: string };
    if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : t.loadError);
    setGoals(body.goals ?? []);
  }

  useEffect(() => {
    let active = true;
    void fetch("/api/stagecoach/goals", { cache: "no-store" })
      .then(async (response) => {
        const body = (await response.json()) as { goals?: GoalRow[]; detail?: string };
        if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : t.loadError);
        if (active) setGoals(body.goals ?? []);
      })
      .catch((reason: Error) => {
        if (active) setError(reason.message);
      });
    return () => {
      active = false;
    };
  }, [t]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const formEl = event.currentTarget;
    const form = new FormData(formEl);
    const key = String(form.get("key") || "").trim();
    const comparator = String(form.get("comparator") || "<");
    const target = Number(form.get("target"));
    try {
      const response = await fetch("/api/stagecoach/goals", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          metric_id: kind === "metric" ? key : null,
          category_id: kind === "category" ? key : null,
          comparator,
          target,
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : t.createError);
      await load();
      formEl.reset();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t.createError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-lg border p-4" data-testid="goals-panel">
      <h2 className="mb-1 text-sm font-semibold">{t.heading}</h2>
      <p className="mb-4 text-sm text-muted-foreground">{t.intro}</p>
      <form onSubmit={(event) => void create(event)} className="mb-4 grid gap-3 sm:grid-cols-4">
        <label className="text-sm font-medium">
          {t.kind}
          <select
            value={kind}
            onChange={(event) => setKind(event.target.value as "metric" | "category")}
            className="mt-1 w-full rounded-md border px-3 py-2"
            data-testid="goal-kind"
          >
            <option value="metric">{t.metric}</option>
            <option value="category">{t.category}</option>
          </select>
        </label>
        <label className="text-sm font-medium">
          {kind === "metric" ? t.metric : t.category}
          <input
            name="key"
            required
            placeholder={kind === "metric" ? "fl_filler_sounds_per_min" : "fluency"}
            className="mt-1 w-full rounded-md border px-3 py-2"
            data-testid="goal-key"
          />
        </label>
        <label className="text-sm font-medium">
          {t.comparator}
          <select name="comparator" defaultValue="<" className="mt-1 w-full rounded-md border px-3 py-2">
            <option value="<">&lt;</option>
            <option value="<=">&lt;=</option>
            <option value=">">&gt;</option>
            <option value=">=">&gt;=</option>
            <option value="=">=</option>
          </select>
        </label>
        <label className="text-sm font-medium">
          {t.target}
          <input
            name="target"
            type="number"
            step="any"
            required
            defaultValue={3}
            className="mt-1 w-full rounded-md border px-3 py-2"
            data-testid="goal-target"
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          data-testid="goal-submit"
          className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground sm:col-span-4"
        >
          {t.add}
        </button>
      </form>
      {error ? <p className="mb-2 text-sm text-destructive">{error}</p> : null}
      <ul className="space-y-1 text-sm" data-testid="goals-list">
        {goals.length === 0 ? <li className="text-muted-foreground">{t.empty}</li> : null}
        {goals.map((goal) => (
          <li key={goal.id || goal.label} data-testid="goal-row">
            {goal.label || `${goal.metric_id || goal.category_id} ${goal.comparator} ${goal.target}`}
            {goal.achieved_at ? ` · ${t.achieved}` : ""}
          </li>
        ))}
      </ul>
    </section>
  );
}
