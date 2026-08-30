/**
 * Persistent ops header: where you are, what is outstanding, where you can go.
 *
 * The counters are links, not labels. Each already names a subset of the
 * board, so making it navigate to that subset costs nothing and saves a
 * reader translating "1 critical" into a scan of the queue.
 *
 * The filter lives in the url rather than in component state: it survives the
 * back button, it can be sent to someone, and clicking a counter from the
 * archive or the campus page lands on the queue already narrowed.
 */
import { Link, NavLink, useLocation, useSearchParams } from 'react-router-dom'

export type QueueFilter = 'attention' | 'critical' | 'open'

interface OpsNavProps {
  attention: number
  critical: number
  open: number
}

/** Ops destinations, in the order a coordinator works through them. */
const NAV = [
  { to: '/ops', label: 'Queue', end: true },
  { to: '/ops/archive', label: 'Archive', end: false },
  { to: '/ops/campus', label: 'Campus', end: false },
]

const COUNTS: { key: QueueFilter; label: string }[] = [
  { key: 'attention', label: 'Needs you' },
  { key: 'critical', label: 'Critical' },
  { key: 'open', label: 'Open' },
]

export function OpsNav({ attention, critical, open }: OpsNavProps) {
  const [params] = useSearchParams()
  const location = useLocation()
  // A filter only means anything on the queue; elsewhere the counters are
  // still links, they just carry the reader there.
  const active = location.pathname === '/ops' ? params.get('filter') : null
  const values: Record<QueueFilter, number> = { attention, critical, open }

  return (
    <header className="statusbar">
      {/* The product name only. Naming a campus here would tie the board to
          one deployment; which campus this is belongs on the campus page,
          where the rest of its configuration lives. */}
      <div className="statusbar__brand">
        <Link to="/" className="statusbar__mark wordmark">
          Relay
        </Link>
      </div>

      <div className="statusbar__counts" role="status" aria-live="polite">
        {COUNTS.map((count) => {
          const isActive = active === count.key
          return (
            <Link
              key={count.key}
              // Clicking the active filter clears it, so one target both
              // applies and undoes -- there is no separate "clear" to hunt for.
              to={isActive ? '/ops' : `/ops?filter=${count.key}`}
              className={`count count--link${
                count.key === 'attention' ? ' count--attention' : ''
              }${isActive ? ' count--on' : ''}`}
              aria-pressed={isActive}
              title={
                isActive
                  ? `Showing ${count.label.toLowerCase()} only — click to clear`
                  : `Show ${count.label.toLowerCase()} only`
              }
            >
              <span className="count__value">{values[count.key]}</span>
              <span className="label">{count.label}</span>
            </Link>
          )
        })}
      </div>

      <nav className="statusbar__nav" aria-label="Operations">
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end} className="btn btn--ghost btn--sm">
            {item.label}
          </NavLink>
        ))}
        <Link to="/report" className="btn btn--primary btn--sm">
          New report
        </Link>
      </nav>
    </header>
  )
}
