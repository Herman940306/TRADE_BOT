import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a decimal string for display. Never parses as float.
 * Returns the string as-is, truncated to `decimals` places.
 */
export function formatDecimal(value: string | null | undefined, decimals = 2): string {
  if (!value) return '—';
  const dot = value.indexOf('.');
  if (dot === -1) return value;
  return value.slice(0, dot + decimals + 1);
}

/**
 * Format a ZAR amount string for display.
 */
export function formatZAR(value: string | null | undefined): string {
  if (!value) return 'R —';
  return `R ${formatDecimal(value, 2)}`;
}
