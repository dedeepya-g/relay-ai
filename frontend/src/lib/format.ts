/** Formatting helpers for the structured facts the board displays. */
import type { IncidentSummary, PendingReview, Priority } from './types'

export const PRIORITY_RANK: Record<Priority, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
}

/** Share of an incident's SLA window that counts as "due soon". */
const DUE_SOON_FRACTION = 0.1

/**
 * Floor on the warning window, so a long SLA still gives usable lead time:
 * 10% of 24 hours is over two hours, but 10% of one hour is six minutes.
 */
const DUE_SOON_FLOOR_SECONDS = 15 * 60

/**
 * Ceiling on that floor, expressed as a share of the window.
 *
 * Campus SLAs can be shorter than the floor -- the seeded demo policy runs
 * critical at two minutes -- and without this an incident would be "due soon"
 * from the moment it opened, which says nothing. Capping at half the window
 * keeps the flag meaning "the tail end of this deadline" at every scale.
 */
const DUE_SOON_MAX_SHARE = 0.5

/**
 * The SLA window actually applied to an incident, in seconds.
 *
 * Taken from the incident rather than the campus policy because the backend
 * sets `sla_due_at = created_at + sla_minutes[priority]`, so this stays correct
 * for incidents already open when the policy changes. Null when the incident
 * has no deadline, or when the two timestamps do not bracket a real window.
 */
function slaWindowSeconds(incident: IncidentSummary): number | null {
  if (!incident.sla_due_at) return null
  const total =
    (new Date(incident.sla_due_at).getTime() - new Date(incident.created_at).getTime()) / 1000
  return total > 0 ? total : null
}

/** Seconds before the deadline at which this incident is called out as due soon. */
export function dueSoonSeconds(incident: IncidentSummary): number {
  const total = slaWindowSeconds(incident)
  if (total === null) return DUE_SOON_FLOOR_SECONDS
  return Math.max(
    total * DUE_SOON_FRACTION,
    Math.min(DUE_SOON_FLOOR_SECONDS, total * DUE_SOON_MAX_SHARE),
  )
}

/** Signed seconds until an SLA deadline; negative once it has passed. */
export function secondsUntil(iso: string | null, now: number): number | null {
  if (!iso) return null
  return Math.round((new Date(iso).getTime() - now) / 1000)
}

/**
 * Render a duration as `M:SS`, or `H:MM:SS` once it runs to an hour or more.
 * Prefixed with `+` once it has run over.
 *
 * Colon-delimited rather than `17h 59m` because the SLA cell is mono with
 * tabular figures: all-digit values stay aligned down the column, where a
 * letter-suffixed form would not.
 */
export function formatCountdown(seconds: number): string {
  const over = seconds < 0
  const total = Math.abs(seconds)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const rest = String(total % 60).padStart(2, '0')
  const sign = over ? '+' : ''
  if (hours === 0) return `${sign}${minutes}:${rest}`
  return `${sign}${hours}:${String(minutes).padStart(2, '0')}:${rest}`
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
  if (remaining <= dueSoonSeconds(incident)) return 'due-soon'
  return null
}

export interface AttentionItem {
  reason: AttentionReason
  incident?: IncidentSummary
  review?: PendingReview
}

/**
 * Everything needing a person right now, in the order it should be worked.
 *
 * The single source of truth for what "needs your attention" means. The header
 * counter and the queue band both read from this, so the number in the header
 * can never disagree with the rows underneath it.
 */
export function buildAttention(
  incidents: IncidentSummary[],
  reviews: PendingReview[],
  now: number,
): AttentionItem[] {
  const flagged = incidents
    .map((incident) => ({ incident, reason: attentionReason(incident, now) }))
    .filter(
      (entry): entry is { incident: IncidentSummary; reason: AttentionReason } =>
        entry.reason !== null,
    )

  return sortAttention([
    ...reviews.map((review) => ({ reason: 'review' as const, review })),
    ...flagged.map((entry) => ({ reason: entry.reason, incident: entry.incident })),
  ])
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

/**
 * Every `IssueCategory` the backend can return, written the way a facilities
 * coordinator says it. Kept complete rather than special-casing the awkward
 * ones, because the fallback below title-cases blindly and would render
 * `it_av` as "It_av" and `access` as bare "Access".
 */
const CATEGORY_LABELS: Record<string, string> = {
  plumbing: 'Plumbing',
  electrical: 'Electrical',
  hvac: 'HVAC',
  access: 'Access control',
  custodial: 'Custodial',
  structural: 'Structural',
  safety: 'Safety',
  grounds: 'Grounds',
  it_av: 'IT/AV',
  elevator: 'Elevator',
  pest: 'Pest control',
  other: 'Other',
}

/**
 * Category as a person would write it.
 *
 * The title-case fallback stays as a guard for a category added to the backend
 * enum before this map catches up: an ugly label beats a blank cell.
 */
export function categoryLabel(category: string | null): string {
  if (!category) return 'Unclassified'
  return CATEGORY_LABELS[category] ?? category[0].toUpperCase() + category.slice(1)
}

/**
 * A floor id as a person would say it.
 *
 * Campus floor ids are mostly storey numbers, but basements are lettered, and
 * "Floor B1" is not something anyone says out loud.
 */
export function floorLabel(floor: string): string {
  return floor === 'B1' ? 'Basement' : `Floor ${floor}`
}

/** Location as a single readable line. */
export function locationLine(
  buildingName: string,
  floor: string | null,
  room: string | null,
): string {
  const parts = [buildingName]
  if (room) parts.push(`Room ${room}`)
  else if (floor) parts.push(floorLabel(floor))
  return parts.join(' · ')
}
