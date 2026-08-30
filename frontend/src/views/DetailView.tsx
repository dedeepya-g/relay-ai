/**
 * Incident detail. The ledger is the point of this screen, so it takes the
 * wider column and the metadata sits beside it rather than above it.
 */
import { useEffect, useState } from 'react'

import { AttentionTag } from '../components/AttentionTag'
import { DecisionLedger } from '../components/DecisionLedger'
import { PriorityToken } from '../components/PriorityToken'
import { getWorkOrder } from '../lib/api'
import {
  categoryLabel,
  formatCountdown,
  locationLine,
  secondsUntil,
  statusLabel,
} from '../lib/format'
import type {
  Campus,
  IncidentDetail,
  IncidentStatus,
  IncidentSummary,
  WorkOrder,
  WorkOrderStatus,
} from '../lib/types'

interface DetailProps {
  detail: IncidentDetail
  campus: Campus | null
  now: number
  onBack: () => void
  onChangeStatus: (
    incidentId: string,
    newStatus: IncidentStatus,
    notes?: string,
  ) => Promise<void>
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="label">{label}</span>
      <p className="fact__value">{value}</p>
    </div>
  )
}

interface StatusAction {
  label: string
  target: IncidentStatus
  /** Resolving writes the incident's resolution notes, so it cannot be blank. */
  requiresNote: boolean
}

const RESOLVE: StatusAction = { label: 'Resolve', target: 'resolved', requiresNote: true }

/**
 * The moves offered from each status.
 *
 * A deliberate subset of the server's `ALLOWED_TRANSITIONS`: this offers the
 * step a coordinator actually takes next, not every legal move. The server
 * still refuses anything illegal, so narrowing here costs no safety. Statuses
 * absent from this map offer nothing -- `closed` is terminal, and `open` means
 * dispatch has not run yet, which is Relay's job rather than a person's.
 */
const NEXT_ACTIONS: Partial<Record<IncidentStatus, StatusAction[]>> = {
  assigned: [{ label: 'Start work', target: 'in_progress', requiresNote: false }, RESOLVE],
  in_progress: [RESOLVE],
  on_hold: [RESOLVE],
  escalated: [RESOLVE],
  resolved: [{ label: 'Close', target: 'closed', requiresNote: false }],
}

const WORK_ORDER_STATUS_LABELS: Record<WorkOrderStatus, string> = {
  pending: 'Pending',
  acknowledged: 'Acknowledged',
  in_progress: 'In progress',
  completed: 'Completed',
  cancelled: 'Cancelled',
}

/**
 * The tickets dispatched for this incident.
 *
 * Read-only: Relay raises a work order, and the crew updates it in the system
 * that owns the field work, so this reports rather than edits. Fetched per id
 * because the incident carries ids only -- a screen that does not show them
 * should not pay to load them.
 */
function WorkOrderCard({ incident }: { incident: IncidentSummary }) {
  const [orders, setOrders] = useState<WorkOrder[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const ids = incident.work_order_ids
  const key = ids.join(',')

  useEffect(() => {
    if (ids.length === 0) {
      setOrders([])
      return
    }
    let cancelled = false
    void (async () => {
      try {
        const loaded = await Promise.all(ids.map((id) => getWorkOrder(id)))
        if (!cancelled) {
          setOrders(loaded)
          setError(null)
        }
      } catch (caught) {
        if (!cancelled) {
          setOrders([])
          setError(
            caught instanceof Error ? caught.message : 'Could not load work orders.',
          )
        }
      }
    })()
    return () => {
      cancelled = true
    }
    // Keyed on the joined ids so a re-render with the same tickets does not refetch.
  }, [key])

  return (
    <div className="panel">
      <div className="panel__head">
        <h2 className="panel__title">Work orders</h2>
        {orders !== null && orders.length > 0 && (
          <span className="label">
            {orders.length} {orders.length === 1 ? 'ticket' : 'tickets'}
          </span>
        )}
      </div>

      {orders === null ? (
        <div className="empty">Loading…</div>
      ) : orders.length === 0 ? (
        <div className="empty">
          <strong>No work order yet.</strong>
          {error ??
            'Relay raises one once the incident has a team. Incidents from before ' +
              'dispatch recorded this link show nothing here.'}
        </div>
      ) : (
        <div className="evidence">
          {orders.map((order) => (
            <div className="evidence__item" key={order.work_order_id}>
              <div className="evidence__meta" style={{ marginBottom: '0.375rem' }}>
                <span className="fact__value" style={{ marginTop: 0 }}>
                  {order.ticket}
                </span>
                <span className="tag">{WORK_ORDER_STATUS_LABELS[order.status]}</span>
              </div>
              <div className="factgrid" style={{ padding: 0 }}>
                <Fact label="Team" value={order.team_name ?? order.team_id} />
                <Fact
                  label="Due"
                  value={
                    order.due_at
                      ? new Date(order.due_at).toLocaleString([], {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                          hour12: false,
                        })
                      : '—'
                  }
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * Status changes, confirmed in place.
 *
 * Expands inline rather than opening a dialog, matching how a paused report is
 * resolved in the queue: the reasoning stays on screen beside the decision
 * being made.
 */
function ActionsPanel({
  incident,
  onChangeStatus,
}: {
  incident: IncidentSummary
  onChangeStatus: DetailProps['onChangeStatus']
}) {
  const [pending, setPending] = useState<StatusAction | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const actions = NEXT_ACTIONS[incident.status] ?? []

  function start(action: StatusAction) {
    setPending(action)
    setNote('')
    setError(null)
  }

  async function confirm() {
    if (!pending) return
    setBusy(true)
    setError(null)
    try {
      await onChangeStatus(incident.incident_id, pending.target, note)
      setPending(null)
      setNote('')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'That did not go through.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel">
      <div className="panel__head">
        <h2 className="panel__title">Actions</h2>
        <span className="label">{statusLabel(incident.status)}</span>
      </div>

      {actions.length === 0 ? (
        <div className="empty">
          <strong>Nothing to do here.</strong>
          {incident.status === 'closed'
            ? 'This incident is closed.'
            : 'Relay dispatches this incident once it has a team.'}
        </div>
      ) : (
        <div style={{ padding: '0.875rem 1rem 1rem' }}>
          {pending ? (
            <div className="enter">
              <div className="field" style={{ marginBottom: '0.875rem' }}>
                <label className="label" htmlFor="status-note">
                  {pending.requiresNote ? (
                    'What was done'
                  ) : (
                    <>
                      Note <span style={{ textTransform: 'none' }}>· optional</span>
                    </>
                  )}
                </label>
                <input
                  id="status-note"
                  className="input"
                  type="text"
                  value={note}
                  maxLength={2000}
                  disabled={busy}
                  autoFocus
                  placeholder={
                    pending.requiresNote
                      ? 'Replaced the supply line and dried the floor.'
                      : 'Anything worth recording'
                  }
                  onChange={(event) => setNote(event.target.value)}
                />
                {pending.requiresNote && (
                  <p className="hint">
                    Recorded as this incident's resolution notes, so it needs to say
                    what was actually done.
                  </p>
                )}
              </div>

              <div className="review__actions">
                <button
                  type="button"
                  className="btn btn--primary btn--sm"
                  disabled={busy || (pending.requiresNote && note.trim().length === 0)}
                  onClick={() => void confirm()}
                >
                  {busy ? 'Saving…' : `Confirm ${pending.label.toLowerCase()}`}
                </button>
                <button
                  type="button"
                  className="btn btn--sm"
                  disabled={busy}
                  onClick={() => {
                    setPending(null)
                    setError(null)
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="review__actions">
              {actions.map((action) => (
                <button
                  key={action.target}
                  type="button"
                  className="btn btn--sm"
                  onClick={() => start(action)}
                >
                  {action.label}
                </button>
              ))}
            </div>
          )}

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

export function DetailView({
  detail,
  campus,
  now,
  onBack,
  onChangeStatus,
}: DetailProps) {
  const { incident, reports, decisions, summary } = detail
  const building =
    campus?.buildings.find((item) => item.building_id === incident.building_id)?.name ??
    incident.building_id
  const remaining = secondsUntil(incident.sla_due_at, now)

  return (
    <>
      <button type="button" className="btn btn--ghost btn--sm" onClick={onBack}>
        ← Back to queue
      </button>

      <div className="detail__head">
        <h1 className="detail__title">{incident.title}</h1>
        <PriorityToken priority={incident.priority} />
        {incident.escalation_level ? <AttentionTag reason="escalated" /> : null}
        <span className="idtag">{incident.incident_id}</span>
      </div>
      <p className="hint" style={{ marginBottom: '1.25rem' }}>
        {locationLine(building, incident.floor, incident.room)} ·{' '}
        {categoryLabel(incident.category)} · {statusLabel(incident.status)}
      </p>

      <div className="detail__grid">
        <div>
          <div className="panel">
            <div className="panel__head">
              <h2 className="panel__title">What happened</h2>
              <span className="label">
                {decisions.length} {decisions.length === 1 ? 'decision' : 'decisions'}
              </span>
            </div>
            <DecisionLedger
              reports={reports}
              decisions={decisions}
              buildingName={building}
            />
          </div>
        </div>

        <aside style={{ display: 'grid', gap: '1.25rem' }}>
          <div className="panel">
            <div className="panel__head">
              <h2 className="panel__title">Status</h2>
            </div>
            <div className="factgrid">
              <Fact label="Team" value={incident.assigned_team_name ?? 'Unassigned'} />
              <Fact
                label="Evidence"
                value={`${incident.report_count} ${
                  incident.report_count === 1 ? 'report' : 'reports'
                }`}
              />
              <Fact
                label={remaining !== null && remaining < 0 ? 'Past deadline' : 'Deadline in'}
                value={remaining === null ? '—' : formatCountdown(remaining)}
              />
              {/* Shown only once raised: a level of zero is the normal case and
                  would just be a column of noughts on every other incident. */}
              {incident.escalation_level ? (
                <Fact label="Escalation" value={`Level ${incident.escalation_level}`} />
              ) : null}
            </div>
          </div>

          <ActionsPanel incident={incident} onChangeStatus={onChangeStatus} />

          <WorkOrderCard incident={incident} />

          <div className="panel">
            <div className="panel__head">
              <h2 className="panel__title">Reports</h2>
              <span className="label">{reports.length} linked</span>
            </div>
            <div className="evidence">
              {reports.length === 0 ? (
                <div className="empty">
                  <strong>No reports linked yet.</strong>
                </div>
              ) : (
                reports.map((report) => (
                  <div className="evidence__item" key={report.report_id}>
                    <p className="evidence__text">“{report.description}”</p>
                    <div className="evidence__meta">
                      <span className="label">
                        {locationLine(building, report.floor, report.room)}
                      </span>
                      {report.is_potential_emergency && (
                        <span className="tag tag--overdue">Danger</span>
                      )}
                    </div>
                    {report.severity_signals.length > 0 && (
                      <p className="hint" style={{ marginTop: '0.3125rem' }}>
                        Signals: {report.severity_signals.join('; ')}
                      </p>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="panel">
            <div className="panel__head">
              <h2 className="panel__title">Summary</h2>
            </div>
            <p style={{ padding: '0.875rem 1rem', fontSize: '0.875rem', whiteSpace: 'pre-line' }}>
              {summary}
            </p>
          </div>
        </aside>
      </div>
    </>
  )
}
