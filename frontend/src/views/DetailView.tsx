/**
 * Incident detail. The ledger is the point of this screen, so it takes the
 * wider column and the metadata sits beside it rather than above it.
 */
import { DecisionLedger } from '../components/DecisionLedger'
import { PriorityToken } from '../components/PriorityToken'
import { categoryLabel, formatCountdown, locationLine, secondsUntil } from '../lib/format'
import type { Campus, IncidentDetail } from '../lib/types'

interface DetailProps {
  detail: IncidentDetail
  campus: Campus | null
  now: number
  onBack: () => void
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="label">{label}</span>
      <p className="fact__value">{value}</p>
    </div>
  )
}

export function DetailView({ detail, campus, now, onBack }: DetailProps) {
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
        <span className="idtag">{incident.incident_id}</span>
      </div>
      <p className="hint" style={{ marginBottom: '1.25rem' }}>
        {locationLine(building, incident.floor, incident.room)} ·{' '}
        {categoryLabel(incident.category)} · {incident.status.replace('_', ' ')}
      </p>

      <div className="detail__grid">
        <div>
          <div className="panel">
            <div className="panel__head">
              <h2 className="panel__title">Decision trail</h2>
              <span className="label">
                {decisions.length} {decisions.length === 1 ? 'decision' : 'decisions'} ·
                grouped by report
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
            </div>
          </div>

          <div className="panel">
            <div className="panel__head">
              <h2 className="panel__title">What was reported</h2>
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
              <h2 className="panel__title">Consolidated summary</h2>
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
