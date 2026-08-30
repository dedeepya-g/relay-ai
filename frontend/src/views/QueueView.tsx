/**
 * The queue: the main working view.
 *
 * Two bands. Everything that cannot wait sits at the top, each row tagged with
 * why it is there, so the band stays readable even when most rows share a
 * reason. Below it, the rest of the board grouped by the team that owns it.
 */
import { useState } from 'react'

import { AttentionTag } from '../components/AttentionTag'
import { ClearBoard } from '../components/ClearBoard'
import { PriorityToken } from '../components/PriorityToken'
import {
  buildAttention,
  dueSoonSeconds,
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
  /**
   * Render one flat list instead of the attention band and team groups.
   *
   * Grouping answers "what should I pick up next" from the whole board. Once
   * a reader has narrowed it themselves, that question is already answered
   * and the groups only fragment a short list.
   */
  flat?: boolean
  /** What to say when the list is empty because of narrowing, not calm. */
  emptyNote?: string
}

function buildingName(campus: Campus | null, buildingId: string): string {
  return (
    campus?.buildings.find((building) => building.building_id === buildingId)?.name ??
    buildingId
  )
}

function IncidentRow({
  incident,
  now,
  campus,
  onOpen,
}: {
  incident: IncidentSummary
  now: number
  campus: Campus | null
  onOpen: (id: string) => void
}) {
  const remaining = secondsUntil(incident.sla_due_at, now)
  const raised = (incident.escalation_level ?? 0) > 0
  const over = remaining !== null && remaining < 0
  const soon = remaining !== null && !over && remaining <= dueSoonSeconds(incident)

  return (
    <button type="button" className="row enter" onClick={() => onOpen(incident.incident_id)}>
      <PriorityToken priority={incident.priority} />

      <span className="row__main">
        <span className="row__title">{incident.title}</span>
        {/* The row carries four things; everything else waits in the detail
            view. What it cannot carry, it reveals on focus rather than
            crowding every row permanently. */}
        <span className="row__peek">{incident.summary}</span>
      </span>

      <span className="row__where">
        {locationLine(
          buildingName(campus, incident.building_id),
          incident.floor,
          incident.room,
        )}
      </span>

      <span className={`row__sla${over ? ' row__sla--over' : soon ? ' row__sla--soon' : ''}`}>
        {raised && <span className="dot dot--raised" aria-label="Raised" />}
        {!raised && soon && <span className="dot dot--soon" aria-label="Due soon" />}
        {remaining === null ? '—' : formatCountdown(remaining)}
      </span>
    </button>
  )
}

/** The manual overdue sweep, with whatever the last run reported. */
function SweepButton({
  sweeping,
  note,
  onRun,
}: {
  sweeping: boolean
  note: string | null
  onRun: () => Promise<void>
}) {
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
      {note && (
        <span className="hint" role="status" aria-live="polite">
          {note}
        </span>
      )}
      <button
        type="button"
        className="btn btn--sm"
        disabled={sweeping}
        onClick={() => void onRun()}
      >
        {sweeping ? 'Checking…' : 'Check overdue'}
      </button>
    </span>
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
  flat = false,
  emptyNote,
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

  if (flat) {
    return (
      <>
        <div className="section-head">
          <h2 className="panel__title">Results</h2>
          <span className="label">
            {incidents.length} {incidents.length === 1 ? 'incident' : 'incidents'}
          </span>
          <span style={{ marginLeft: 'auto' }}>
            <SweepButton sweeping={sweeping} note={sweepNote} onRun={runSweep} />
          </span>
        </div>
        <div className="panel">
          {incidents.length === 0 ? (
            <div className="empty empty--art">
              <ClearBoard />
              <strong>Nothing to show.</strong>
              {emptyNote ?? 'No incidents match.'}
            </div>
          ) : (
            incidents.map((incident) => (
              <IncidentRow
                key={incident.incident_id}
                incident={incident}
                now={now}
                campus={campus}
                onOpen={onOpen}
              />
            ))
          )}
        </div>
      </>
    )
  }

  return (
    <>
      <div className="section-head">
        <h2 className="panel__title">Needs you</h2>
        <span className="label">{attention.length} of {incidents.length + reviews.length}</span>
        <span style={{ marginLeft: 'auto' }}>
          <SweepButton sweeping={sweeping} note={sweepNote} onRun={runSweep} />
        </span>
      </div>

      <div className={`panel attention${attention.length === 0 ? ' attention--calm' : ''}`}>
        {attention.length === 0 ? (
          <div className="empty empty--art">
            <ClearBoard />
            <strong>All clear.</strong>
            Nothing is waiting on you.
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
                campus={campus}
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
            <div className="empty empty--art">
              <ClearBoard />
              <strong>Nothing open.</strong>
              New reports land here as they come in.
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
                  campus={campus}
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
