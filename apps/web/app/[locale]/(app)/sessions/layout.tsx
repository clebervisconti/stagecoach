import { titled } from "@/lib/titles";

export function generateMetadata() {
  return titled("Sessions", "Sessões");
}

export default function SessionsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
