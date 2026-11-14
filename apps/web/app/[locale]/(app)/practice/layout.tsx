import { titled } from "@/lib/titles";

export function generateMetadata() {
  return titled("Practice", "Prática");
}

export default function PracticeLayout({ children }: { children: React.ReactNode }) {
  return children;
}
