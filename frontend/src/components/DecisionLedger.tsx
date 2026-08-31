/**
 * What happened to this incident, and why.
 *
 * Written to read like a colleague's notes rather than a system log. Each
 * entry leads with what was decided, in plain words, and carries the reasoning
 * underneath. Nothing names the machinery: a reader wants to know the report
 * was sorted as plumbing, not which component sorted it.
 *
 * The one distinction worth keeping is whether a person was involved, and it
 * is carried by placement -- a person's note steps out of the column and takes
 * a filled marker -- rather than by a label repeating it on every row.
 *
 * (original note follows)
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

/**
 * What a decision did, in the words a coordinator would use.
 *
 * Built from the stored outcome, because the outcome names the specific thing
 * decided and the type alone does not: "deduplication" is a category, "added
 * to an existing issue" is what actually happened.
 */
export function headline(entry: DecisionEntry): string {
  const outcome = entry.outcome ?? ''
  const tidy = (value: string) =>
    value
      .replace(/^team_/, '')
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase())

  switch (entry.decision_type) {
    case 'triage': {
      const category = outcome.match(/classified as ([a-z_]+)/)?.[1]
      return category ? `Sorted as ${tidy(category)}` : 'Read the report'
    }
    case 'deduplication':
      if (outcome.includes('merged')) return 'Added to an existing issue'
      if (outcome.includes('needs_review')) return 'Held for someone to check'
      if (outcome.includes('opened') || outcome.includes('new_incident'))
        return 'Opened a new issue'
      return 'Checked against open issues'
    case 'prioritization': {
      const level = outcome.match(/(critical|high|medium|low)/)?.[1]
      return level ? `Set to ${tidy(level)}` : 'Set the priority'
    }
    case 'routing': {
      const team = outcome.match(/(team_[a-z_]+)/)?.[1]
      return team ? `Sent to ${tidy(team)}` : 'Chose the team'
    }
    case 'escalation':
      return 'Raised, still not picked up'
    case 'resolution':
      if (outcome.includes('to closed')) return 'Closed'
      if (outcome.includes('to resolved')) return 'Marked resolved'
      if (outcome.includes('to in_progress')) return 'Work started'
      if (outcome.includes('to on_hold')) return 'Put on hold'
      return 'Status changed'
    case 'coordination':
      return 'Followed up'
    default:
      return 'Noted'
  }
}

/**
 * Who made this call, phrased for someone reading a record.
 *
 * Shown only inside an opened entry. The distinction matters when a decision
 * is questioned, and never enough to earn a badge on a line that is scanned.
 */
function decidedBy(entry: DecisionEntry): string {
  switch (entry.decided_by) {
    case 'human':
      return 'Decided by a person.'
    case 'rule':
      return 'Applied from campus policy.'
    default:
      return 'Decided by Relay.'
  }
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
<strong>Nothing recorded yet.</strong>
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
            <p className="event__meta">On the issue itself</p>
          )}

          {item.entries.map((entry) => (
            <details
              key={entry.decision_id}
              className={`entry entry--${entry.decided_by}`}
            >
              {/* One line by default. These already happened, so the resting
                  state is a record rather than a paragraph to read. */}
              <summary className="entry__head">
                <span className="entry__what">
                  {headline(entry)}
                  {entry.decided_by === 'human' && (
                    <span className="entry__who"> · by someone here</span>
                  )}
                </span>
                <span className="entry__at">{formatClock(entry.created_at)}</span>
              </summary>
              <div className="entry__detail">
                <p className="entry__why">{entry.rationale}</p>
                {/* Who made the call, for the reader who opens an entry and
                    asks. Never the headline. */}
                <p className="entry__by">{decidedBy(entry)}</p>
              </div>
            </details>
          ))}
        </section>
      ))}
    </div>
  )
}
