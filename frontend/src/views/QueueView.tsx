/**
 * The queue: the main working view.
 *
 * Two bands. Everything that cannot wait sits at the top, each row tagged with
 * why it is there, so the band stays readable even when most rows share a
 * reason. Below it, the rest of the board grouped by the team that owns it.
 */
import { useState } from 'react'

import { AttentionTag } from '../components/AttentionTag'
import { PriorityToken } from '../components/PriorityToken'
import {
  type AttentionReason,
  buildAttention,
  floorLabel,
  formatAge,
  formatCountdown,
  locationLine,
  PRIORITY_RANK,
  secondsUntil,
} from '../lib/format'
import type {
  Campus,
  IncidentSummary,
  OverdueSweepResult,
  PendingReview,
} from '../lib/types'

interface QueueProps {
  incidents: IncidentSummary[]
  reviews: PendingReview[]
  campus: Campus | null
  now: number
  onOpen: (incidentId: string) => void
  onResolve: (
    reportId: string,
    resolution: 'same_incident' | 'different_incident',
    incidentId?: string,
    note?: string,
  ) => Promise<void>
  onCheckOverdue: () => Promise<OverdueSweepResult>
}

/**
 * The part of a location the row title does not already say.
 *
 * Titles carry the building, so repeating it here would spend a column on
 * something already on screen and truncate the part that is new.
 */
function preciseLocation(incident: IncidentSummary): string {
  if (incident.room) return `Room ${incident.room}`
  if (incident.floor) return floorLabel(incident.floor)
  return 'Location not given'
}

function buildingName(campus: Campus | null, buildingId: string): string {
  return (
    campus?.buildings.find((building) => building.building_id === buildingId)?.name ??
    buildingId
  )
}

function SlaCell({ incident, now }: { incident: IncidentSummary; now: number }) {
  const remaining = secondsUntil(incident.sla_due_at, now)
  if (remaining === null) return <span className="row__sla">—</span>
  const tone = remaining < 0 ? ' row__sla--over' : remaining <= 60 ? ' row__sla--soon' : ''
  return (
    <span className={`row__sla${tone}`}>
      {formatCountdown(remaining)}
      <span className="label" style={{ display: 'block', letterSpacing: '0.06em' }}>
        {remaining < 0 ? 'over' : 'left'}
      </span>
    </span>
  )
}

function IncidentRow({
  incident,
  now,
  reason,
  secondary,
  onOpen,
}: {
  incident: IncidentSummary
  now: number
  reason?: AttentionReason
  secondary: string
  onOpen: (id: string) => void
}) {
  return (
    <button type="button" className="row enter" onClick={() => onOpen(incident.incident_id)}>
      {/* Escalation is read from `escalation_level`, not from the status field,
          matching `attentionReason`. A row carries it wherever it appears, and
          the band's own reason tag is suppressed when it would only repeat it. */}
      <span className="row__flags">
        {incident.escalation_level ? <AttentionTag reason="escalated" /> : null}
        {reason && reason !== 'escalated' && <AttentionTag reason={reason} />}
        <PriorityToken priority={incident.priority} />
      </span>
      <span className="row__main">
        <span className="row__title">{incident.title}</span>
        <span className="row__sub">{incident.incident_id}</span>
      </span>
      <span className="row__team">{secondary}</span>
      <span className="row__num">
        {incident.report_count} {incident.report_count === 1 ? 'report' : 'reports'}
      </span>
      <SlaCell incident={incident} now={now} />
    </button>
  )
}

function ReviewRow({
  review,
  incidents,
  campus,
  now,
  onResolve,
}: {
  review: PendingReview
  incidents: IncidentSummary[]
  campus: Campus | null
  now: number
  onResolve: QueueProps['onResolve']
}) {
  const [open, setOpen] = useState(false)
  const [target, setTarget] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function act(
    resolution: 'same_incident' | 'different_incident',
    incidentId?: string,
  ) {
    setBusy(true)
    setError(null)
    try {
      await onResolve(review.report_id, resolution, incidentId, note)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'That did not go through.')
      setBusy(false)
    }
  }

  return (
    <div className="review enter">
      <button
        type="button"
        className="review__head"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="row__flags">
          <AttentionTag reason="review" />
        </span>
        <span className="row__main">
          <span className="row__title">“{review.description}”</span>
          <span className="row__sub">
            {locationLine(buildingName(campus, review.building_id), review.floor, review.room)}
          </span>
        </span>
        <span className="row__sla">{formatAge(review.submitted_at, now)}</span>
      </button>

      {open && (
        <div className="review__body">
          <p className="review__why">
            <span className="label" style={{ display: 'block', marginBottom: '0.25rem' }}>
              Why Relay stopped
            </span>
            {review.reasoning || 'Relay could not place this report against an open incident.'}
          </p>

          {/* The note is written into the permanent decision trail, so it asks
              for the reviewer's own words. Left blank, the server records its
              default rationale rather than a sentence nobody wrote. */}
          <div className="field" style={{ marginBottom: '0.875rem', maxWidth: '60ch' }}>
            <label className="label" htmlFor={`note-${review.report_id}`}>
              Your reasoning <span style={{ textTransform: 'none' }}>· optional</span>
            </label>
            <input
              id={`note-${review.report_id}`}
              className="input"
              type="text"
              value={note}
              maxLength={2000}
              disabled={busy}
              placeholder="Resolved from the facilities dashboard."
              onChange={(event) => setNote(event.target.value)}
            />
          </div>

          <div className="review__actions">
            <select
              className="select"
              value={target}
              onChange={(event) => setTarget(event.target.value)}
              aria-label="Incident this report belongs to"
              disabled={busy || incidents.length === 0}
            >
              <option value="">Choose the incident it belongs to…</option>
              {incidents.map((incident) => (
                <option key={incident.incident_id} value={incident.incident_id}>
                  {incident.title} · {incident.report_count} reports
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn btn--primary btn--sm"
              disabled={!target || busy}
              onClick={() => act('same_incident', target)}
            >
              Confirm same incident
            </button>
            <button
              type="button"
              className="btn btn--sm"
              disabled={busy}
              onClick={() => act('different_incident')}
            >
              Confirm separate incident
            </button>
          </div>

          {error && (
            <p className="hint" style={{ color: 'var(--critical)', marginTop: '0.625rem' }}>
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export function QueueView({
  incidents,
  reviews,
  campus,
  now,
  onOpen,
  onResolve,
  onCheckOverdue,
}: QueueProps) {
  const [sweeping, setSweeping] = useState(false)
  const [sweepNote, setSweepNote] = useState<string | null>(null)

  /**
   * Relay is meant to run this on a schedule; nothing schedules it yet, so the
   * board offers it by hand. The counts are reported separately because they
   * differ for a reason worth seeing: an incident inside its grace period or
   * repeat interval is overdue but deliberately not raised.
   */
  async function runSweep() {
    setSweeping(true)
    setSweepNote(null)
    try {
      const result = await onCheckOverdue()
      setSweepNote(
        result.escalated_count > 0
          ? `Escalated ${result.escalated_count} of ${result.checked_count} overdue`
          : result.checked_count > 0
            ? `${result.checked_count} overdue, none due to be raised yet`
            : 'Nothing past its deadline',
      )
    } catch (caught) {
      setSweepNote(caught instanceof Error ? caught.message : 'The sweep did not run.')
    } finally {
      setSweeping(false)
    }
  }

  const attention = buildAttention(incidents, reviews, now)

  const flaggedIds = new Set(
    attention.flatMap((item) => (item.incident ? [item.incident.incident_id] : [])),
  )
  const rest = incidents.filter((incident) => !flaggedIds.has(incident.incident_id))

  const byTeam = new Map<string, IncidentSummary[]>()
  for (const incident of rest) {
    const team = incident.assigned_team_name ?? 'Unassigned'
    byTeam.set(team, [...(byTeam.get(team) ?? []), incident])
  }
  for (const list of byTeam.values()) {
    list.sort(
      (a, b) =>
        PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority] ||
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    )
  }

  return (
    <>
      <div className="section-head">
        <h2 className="panel__title">Needs your attention</h2>
        <span className="label">{attention.length} of {incidents.length + reviews.length}</span>
        <span
          style={{
            marginLeft: 'auto',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          {sweepNote && (
            <span className="hint" role="status" aria-live="polite">
              {sweepNote}
            </span>
          )}
          <button
            type="button"
            className="btn btn--sm"
            disabled={sweeping}
            onClick={() => void runSweep()}
          >
            {sweeping ? 'Checking…' : 'Check overdue'}
          </button>
        </span>
      </div>

      <div className={`panel attention${attention.length === 0 ? ' attention--calm' : ''}`}>
        {attention.length === 0 ? (
          <div className="empty">
            <strong>Nothing is waiting on you.</strong>
            Relay placed every report on its own, and no incident has passed its deadline.
          </div>
        ) : (
          attention.map((item) =>
            item.review ? (
              <ReviewRow
                key={item.review.report_id}
                review={item.review}
                incidents={incidents}
                campus={campus}
                now={now}
                onResolve={onResolve}
              />
            ) : (
              <IncidentRow
                key={item.incident!.incident_id}
                incident={item.incident!}
                now={now}
                reason={item.reason}
                secondary={item.incident!.assigned_team_name ?? 'Unassigned'}
                onOpen={onOpen}
              />
            ),
          )
        )}
      </div>

      {rest.length === 0 && incidents.length === 0 ? (
        <>
          <div className="section-head">
            <h2 className="panel__title">Open incidents</h2>
          </div>
          <div className="panel">
            <div className="empty">
              <strong>No open incidents on campus.</strong>
              Relay is watching{' '}
              {campus?.buildings.map((building) => building.name).join(', ') ??
                'this campus'}
              . Submitted reports appear here once they are classified.
            </div>
          </div>
        </>
      ) : (
        [...byTeam.entries()].map(([team, list]) => (
          <section key={team}>
            <div className="section-head">
              <h2 className="panel__title">{team}</h2>
              <span className="label">
                {list.length} {list.length === 1 ? 'incident' : 'incidents'}
              </span>
            </div>
            <div className="panel">
              {list.map((incident) => (
                <IncidentRow
                  key={incident.incident_id}
                  incident={incident}
                  now={now}
                  secondary={preciseLocation(incident)}
                  onOpen={onOpen}
                />
              ))}
            </div>
          </section>
        ))
      )}
    </>
  )
}
