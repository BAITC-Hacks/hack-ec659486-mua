import { clsx, type ClassValue } from "clsx";

/** Склейка классов Tailwind: cn("px-2", cond && "font-bold", className). */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}
