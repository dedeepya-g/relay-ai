/**
 * The decision ledger.
 *
 * Decisions are grouped under the report whose arrival triggered them, because
 * the API returns them as one flat sequence and a flat sequence of fifteen
 * entries is close to unreadable. Grouped, the trail reads as events: when
 * this report arrived, here is what Relay did and why.
 *
 * Agent decisions sit on the spine. Human decisions step into their own lane
 * with a filled marker and a heavier rule, so a reader can see where a person
 * intervened before reading a word.
 */
import { formatClock, locationLine } from '../lib/format'
import type { DecisionEntry, LinkedReport } from '../lib/types'

const TYPE_LABELS: Record<string, string> = {
  triage: 'Triage',
  deduplication: 'Deduplication',
  prioritization: 'Priority',
  routing: 'Routing',
  escalation: 'Escalation',
  resolution: 'Resolution',
}

interface Group {
  report: LinkedReport | null
  entries: DecisionEntry[]
}

/** Group decisions by the report they were made about, in arrival order. */
function group(reports: LinkedReport[], decisions: DecisionEntry[]): Group[] {
  const byReport = new Map<string, DecisionEntry[]>()
  const unattached: DecisionEntry[] = []

  for (const decision of decisions) {
    const owner = reports.find((report) => report.report_id === decision.subject_id)
    if (owner) {
      byReport.set(owner.report_id, [...(byReport.get(owner.report_id) ?? []), decision])
    } else {
      unattached.push(decision)
    }
  }

  // Incident-level decisions (priority, routing) name the incident, not a
  // report. Fold each one into the report it followed, so a group reads as the
  // full consequence of one arrival.
  const groups: Group[] = reports.map((report) => ({
    report,
    entries: byReport.get(report.report_id) ?? [],
  }))

  for (const decision of unattached) {
    const at = new Date(decision.created_at).getTime()
    let target = groups[0]
    for (const candidate of groups) {
      if (candidate.report && new Date(candidate.report.submitted_at).getTime() <= at) {
        target = candidate
      }
    }
    if (target) target.entries.push(decision)
    else groups.push({ report: null, entries: [decision] })
  }

  for (const item of groups) {
    item.entries.sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    )
  }
  return groups.filter((item) => item.entries.length > 0)
}

interface LedgerProps {
  reports: LinkedReport[]
  decisions: DecisionEntry[]
  buildingName: string
}

export function DecisionLedger({ reports, decisions, buildingName }: LedgerProps) {
  const groups = group(reports, decisions)

  if (groups.length === 0) {
    return (
      <div className="empty">
        <strong>No decisions recorded yet.</strong>
        Relay writes an entry here every time it classifies, merges, prioritizes, or
        routes this incident.
      </div>
    )
  }

  return (
    <div className="ledger">
      {groups.map((item, index) => (
        <section className="event" key={item.report?.report_id ?? `group-${index}`}>
          <span className="event__marker" aria-hidden="true" />
          {item.report ? (
            <>
              <p className="event__quote">“{item.report.description}”</p>
              <p className="event__meta">
                {formatClock(item.report.submitted_at)} ·{' '}
                {locationLine(buildingName, item.report.floor, item.report.room)}
              </p>
            </>
          ) : (
            <p className="event__meta">Incident-level decisions</p>
          )}

          {item.entries.map((entry) => (
            <article
              key={entry.decision_id}
              className={`entry${entry.decided_by === 'human' ? ' entry--human' : ''}`}
            >
              <div className="entry__head">
                <span className="entry__type">
                  {TYPE_LABELS[entry.decision_type] ?? entry.decision_type}
                </span>
                <span className="entry__by">
                  {entry.decided_by === 'human' ? 'Person' : 'Relay'}
                </span>
                {/* A null model means "no model was involved". For an agent that
                    reads as a rule; for a person it would misdescribe the
                    decision, and the PERSON chip already says who decided. */}
                {entry.decided_by === 'agent' && (
                  <span className="entry__attr">{entry.model ?? 'rule'}</span>
                )}
              </div>
              <p className="entry__why">{entry.rationale}</p>
            </article>
          ))}
        </section>
      ))}
    </div>
  )
}
