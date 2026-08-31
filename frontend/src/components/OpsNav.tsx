/**
 * The ops header: two places to be, and one thing to do.
 *
 * Everything that competed here has moved to where it belongs. The counters
 * were filters for the queue, so they live on the queue; showing them above
 * the archive meant carrying numbers that could not act on what was on screen.
 * Campus configuration is reference, consulted rarely and never mid-shift, so
 * it sits behind a settings control rather than taking a third of the bar.
 *
 * What remains is the shape of the work: live work, finished work, and adding
 * something new.
 */
import { Link, NavLink } from 'react-router-dom'

export type QueueFilter = 'attention' | 'critical' | 'open'

const NAV = [
  { to: '/ops', label: 'Queue', end: true },
  { to: '/ops/archive', label: 'Archive', end: false },
]

export function OpsNav() {
  return (
    <header className="statusbar">
      <div className="statusbar__brand">
        <Link to="/" className="statusbar__mark wordmark">
          Relay
        </Link>
      </div>

      <nav className="statusbar__nav" aria-label="Operations">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className="btn btn--ghost btn--sm"
          >
            {item.label}
          </NavLink>
        ))}

        {/* Reference, not a destination competing with the two above. */}
        <NavLink to="/ops/campus" className="navicon" title="Campus setup" aria-label="Campus setup">
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor"
               strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="8" cy="8" r="2.1" />
            <path d="M8 1.5v1.8M8 12.7v1.8M14.5 8h-1.8M3.3 8H1.5M12.6 3.4l-1.3 1.3M4.7 11.3l-1.3 1.3M12.6 12.6l-1.3-1.3M4.7 4.7 3.4 3.4" />
          </svg>
        </NavLink>

        <Link to="/report" className="btn btn--primary btn--sm">
          New report
        </Link>
      </nav>
    </header>
  )
}
