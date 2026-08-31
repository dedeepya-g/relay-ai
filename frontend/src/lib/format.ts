/** Formatting helpers for the structured facts the board displays. */
import type { IncidentStatus, IncidentSummary, PendingReview, Priority } from './types'

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

/**
 * An exact date and time, for facts that must be told apart.
 *
 * Relative time collapses: a dozen incidents closed in the same minute all
 * read "31m ago" and become indistinguishable. Where a timestamp identifies a
 * record rather than describing recency, it is shown in full and in mono.
 */
export function formatStamp(iso: string): string {
  return new Date(iso).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
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
 * Escalation is authoritative and comes from the server's overdue sweep. The
 * overdue and due-soon branches are computed client-side from `sla_due_at`,
 * which is what lets a deadline pass on screen between polls without waiting
 * for a sweep to notice.
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
    // Product rule: work someone has actively picked up is never in the
    // attention band, whatever its deadline or escalation level says.
    //
    // The band answers one question -- what is not being dealt with -- and an
    // incident in progress has an answer already. A missed deadline on work
    // underway is a fact about the deadline, not a call to action, and
    // flagging it trains a reader to ignore the band. This is deliberate and
    // permanent, not a way of quieting a noisy board: active human ownership
    // outranks a stale timestamp.
    //
    // The row still shows that it is late. The information is not hidden,
    // it just stops asking for someone.
    .filter((incident) => incident.status !== 'in_progress')
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
 * Every `IncidentStatus` the backend can return, as a coordinator says it.
 *
 * `open` reads as "Queued" rather than "Open": on this board every incident
 * listed is open in the everyday sense, so the enum's word would describe all
 * of them. What `open` actually means is that no work order has been raised
 * yet.
 */
const STATUS_LABELS: Record<IncidentStatus, string> = {
  open: 'Queued',
  assigned: 'Assigned',
  in_progress: 'In progress',
  on_hold: 'On hold',
  escalated: 'Escalated',
  resolved: 'Resolved',
  closed: 'Closed',
}

/** Incident status as a person would write it. */
export function statusLabel(status: IncidentStatus): string {
  return STATUS_LABELS[status] ?? status
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

/** How a list of incidents is ordered. */
export type SortKey = 'priority' | 'newest' | 'oldest'

export const SORT_LABELS: Record<SortKey, string> = {
  priority: 'Priority',
  newest: 'Newest first',
  oldest: 'Oldest first',
}

/**
 * Whether an incident matches a free-text query.
 *
 * Searches the title, the category both raw and as displayed, the id, the
 * owning team, and the summary. The id is there because it is the one string a
 * coordinator copies out of the board and pastes back in; the summary because
 * a row already reveals it on focus, so a reader who has seen those words will
 * reasonably expect to be able to search them.
 */
export function matchesQuery(incident: IncidentSummary, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return (
    incident.title.toLowerCase().includes(q) ||
    incident.category.toLowerCase().includes(q) ||
    categoryLabel(incident.category).toLowerCase().includes(q) ||
    incident.incident_id.toLowerCase().includes(q) ||
    (incident.assigned_team_name ?? '').toLowerCase().includes(q) ||
    (incident.summary ?? '').toLowerCase().includes(q)
  )
}

/**
 * Order incidents without mutating the caller's array.
 *
 * `timeOf` names which timestamp matters for this list: the queue sorts by
 * when work arrived, the archive by when it finished. Priority sorting falls
 * back to recency so equal priorities still have a stable, meaningful order.
 */
export function sortIncidents<T extends IncidentSummary>(
  list: T[],
  key: SortKey,
  timeOf: (incident: T) => string,
): T[] {
  const copy = [...list]
  if (key === 'priority') {
    copy.sort(
      (a, b) =>
        PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority] ||
        new Date(timeOf(b)).getTime() - new Date(timeOf(a)).getTime(),
    )
    return copy
  }
  const direction = key === 'newest' ? -1 : 1
  copy.sort(
    (a, b) => direction * (new Date(timeOf(a)).getTime() - new Date(timeOf(b)).getTime()),
  )
  return copy
}
