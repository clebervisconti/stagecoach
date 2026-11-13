"use client";

import { useParams } from "next/navigation";
import { PlanEditor } from "@/components/prep/plan-editor";
import { SeriesPanel } from "@/components/prep/series-panel";

export default function PlanEditorPage() {
  const params = useParams<{ id: string }>();
  return (
    <div className="container mx-auto max-w-3xl px-4 py-8">
      <PlanEditor planId={params.id} />
      <SeriesPanel planId={params.id} />
    </div>
  );
}
