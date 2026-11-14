import { cn } from "@/components/ui/cn";
import type { SelectHTMLAttributes } from "react";

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn("cs-field", className)} {...props} />;
}
