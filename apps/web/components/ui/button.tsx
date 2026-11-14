import { cn } from "@/components/ui/cn";
import type { ButtonHTMLAttributes } from "react";

const VARIANTS = {
  primary: "cs-button cs-button-primary",
  ghost: "cs-button cs-button-ghost",
  destructive: "cs-button cs-button-destructive",
} as const;

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof VARIANTS;
};

export function Button({ variant = "primary", className, type = "button", ...props }: ButtonProps) {
  return <button type={type} className={cn(VARIANTS[variant], className)} {...props} />;
}
