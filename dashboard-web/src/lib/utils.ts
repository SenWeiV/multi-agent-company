import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDateTime(value?: string | null): string {
  if (!value) {
    return "n/a"
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date)
}

export function compactText(value?: string | null, fallback = "n/a"): string {
  if (!value) {
    return fallback
  }
  return value
}

export function parseCommaList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

export function safeJson(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

export function statusTone(status?: string | null): "success" | "warning" | "destructive" | "default" {
  const normalized = String(status || "").toLowerCase()
  if (["healthy", "ok", "approved", "completed", "go", "sent", "resolved", "ready"].includes(normalized)) {
    return "success"
  }
  if (["warning", "pending", "queued", "blocked", "retrying"].includes(normalized)) {
    return "warning"
  }
  if (["failed", "error", "dead_letter", "quality_no_go", "rejected"].includes(normalized)) {
    return "destructive"
  }
  return "default"
}
