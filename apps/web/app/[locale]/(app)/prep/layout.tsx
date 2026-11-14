import { titled } from "@/lib/titles";

export function generateMetadata() {
  return titled("Talk prep", "Preparação");
}

export default function PrepSectionLayout({ children }: { children: React.ReactNode }) {
  return children;
}
