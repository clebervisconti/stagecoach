import { cn } from "@/components/ui/cn";
import type { InputHTMLAttributes } from "react";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("cs-field", className)} {...props} />;
}
