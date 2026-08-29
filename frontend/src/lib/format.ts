/** Formatting helpers for the structured facts the board displays. */
import type { IncidentSummary, PendingReview, Priority } from './types'

export const PRIORITY_RANK: Record<Priority, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
}

/** Seconds before an SLA deadline at which a row is called out as due soon. */
export const DUE_SOON_SECONDS = 60

/** Signed seconds until an SLA deadline; negative once it has passed. */
export function secondsUntil(iso: string | null, now: number): number | null {
  if (!iso) return null
  return Math.round((new Date(iso).getTime() - now) / 1000)
}

/** Render a duration as `M:SS`, prefixed with `+` once it has run over. */
export function formatCountdown(seconds: number): string {
  const over = seconds < 0
  const total = Math.abs(seconds)
  const minutes = Math.floor(total / 60)
  const rest = String(total % 60).padStart(2, '0')
  return `${over ? '+' : ''}${minutes}:${rest}`
}

/** Time of day, for the ledger. */
export function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

/** Elapsed time in the coarsest unit that still reads truthfully. */
export function formatAge(iso: string, now: number): string {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

export type AttentionReason = 'escalated' | 'review' | 'overdue' | 'due-soon'

export const ATTENTION_LABEL: Record<AttentionReason, string> = {
  escalated: 'Escalated',
  review: 'Review',
  overdue: 'Overdue',
  'due-soon': 'Due soon',
}

/**
 * Why an incident belongs in the attention band, or null if it does not.
 *
 * Computed client-side from `sla_due_at` as an interim measure: the server-side
 * overdue sweep (`escalate_overdue_incidents`) is not implemented, so nothing
 * writes `escalation_level` yet. This is a deliberate stand-in, not a
 * workaround to unpick later -- when that sweep lands, the escalation branch
 * below starts firing on its own and the rest of this stays correct.
 */
export function attentionReason(
  incident: IncidentSummary,
  now: number,
): AttentionReason | null {
  if ((incident.escalation_level ?? 0) > 0) return 'escalated'
  const remaining = secondsUntil(incident.sla_due_at, now)
  if (remaining === null) return null
  if (remaining < 0) return 'overdue'
  if (remaining <= DUE_SOON_SECONDS) return 'due-soon'
  return null
}

export interface AttentionItem {
  reason: AttentionReason
  incident?: IncidentSummary
  review?: PendingReview
}

/**
 * Order the attention band: worst priority first, then longest-waiting.
 *
 * Reports awaiting review sort above incidents regardless of age, because they
 * are the only rows that cannot progress at all without a person.
 */
export function sortAttention(items: AttentionItem[]): AttentionItem[] {
  return [...items].sort((a, b) => {
    if (a.review && !b.review) return -1
    if (b.review && !a.review) return 1
    const rank =
      PRIORITY_RANK[a.incident?.priority ?? 'low'] -
      PRIORITY_RANK[b.incident?.priority ?? 'low']
    if (rank !== 0) return rank
    const aAt = new Date(a.incident?.created_at ?? a.review?.submitted_at ?? 0).getTime()
    const bAt = new Date(b.incident?.created_at ?? b.review?.submitted_at ?? 0).getTime()
    return aAt - bAt
  })
}

const CATEGORY_LABELS: Record<string, string> = {
  hvac: 'HVAC',
  it_av: 'IT/AV',
}

/** Category as a person would write it. */
export function categoryLabel(category: string | null): string {
  if (!category) return 'Unclassified'
  return CATEGORY_LABELS[category] ?? category[0].toUpperCase() + category.slice(1)
}

/** Location as a single readable line. */
export function locationLine(
  buildingName: string,
  floor: string | null,
  room: string | null,
): string {
  const parts = [buildingName]
  if (room) parts.push(`Room ${room}`)
  else if (floor) parts.push(`Floor ${floor}`)
  return parts.join(' · ')
}
