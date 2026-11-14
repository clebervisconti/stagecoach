import { titled } from "@/lib/titles";

export function generateMetadata() {
  return titled("Trends", "Tendências");
}

export default function TrendsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
