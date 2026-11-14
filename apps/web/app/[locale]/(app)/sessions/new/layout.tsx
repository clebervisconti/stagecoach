import { titled } from "@/lib/titles";

export function generateMetadata() {
  return titled("New session", "Nova sessão");
}

export default function NewSessionLayout({ children }: { children: React.ReactNode }) {
  return children;
}
