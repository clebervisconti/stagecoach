import { titled } from "@/lib/titles";

export function generateMetadata() {
  return titled("Session", "Sessão");
}

export default function SessionLayout({ children }: { children: React.ReactNode }) {
  return children;
}
