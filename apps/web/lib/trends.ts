export type TrendPoint = {
  session_id: string;
  title?: string;
  created_at?: string | null;
  context_type?: string;
  language?: string;
  config_version?: string | null;
  comparable: boolean;
  reason?: string | null;
  overall?: number | null;
  value?: number | null;
};

export type TrendsPayload = {
  filters: {
    metric?: string | null;
    category?: string | null;
    context?: string | null;
    language?: string | null;
  };
  series: TrendPoint[];
  sparkline: Array<number | null>;
  most_improved?: { session_id: string; delta: number; from: number; to: number } | null;
  needs_attention?: { session_id: string; delta: number; from: number; to: number } | null;
  comparable_count: number;
};

export function trendsQuery(filters: {
  metric?: string;
  category?: string;
  context?: string;
  language?: string;
}): string {
  const params = new URLSearchParams();
  if (filters.metric) params.set("metric", filters.metric);
  if (filters.category) params.set("category", filters.category);
  if (filters.context) params.set("context", filters.context);
  if (filters.language) params.set("language", filters.language);
  const query = params.toString();
  return query ? `/api/stagecoach/trends?${query}` : "/api/stagecoach/trends";
}

export function sparklinePath(values: Array<number | null>, width = 120, height = 32): string {
  const nums = values.filter((value): value is number => typeof value === "number");
  if (nums.length === 0) return "";
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const span = max - min || 1;
  const step = values.length > 1 ? width / (values.length - 1) : width;
  return values
    .map((value, index) => {
      if (value === null) return null;
      const x = index * step;
      const y = height - ((value - min) / span) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter(Boolean)
    .join(" ");
}
