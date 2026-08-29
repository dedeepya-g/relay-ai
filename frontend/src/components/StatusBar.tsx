/** Persistent header: where you are, what is outstanding, what you can do. */
interface StatusBarProps {
  campusName: string | null
  attention: number
  open: number
  critical: number
  view: 'queue' | 'intake'
  onNavigate: (view: 'queue' | 'intake') => void
}

export function StatusBar({
  campusName,
  attention,
  open,
  critical,
  view,
  onNavigate,
}: StatusBarProps) {
  return (
    <header className="statusbar">
      <div className="statusbar__brand">
        <span className="statusbar__mark">Relay</span>
        <span className="statusbar__campus">{campusName ?? 'Facilities operations'}</span>
      </div>

      <div className="statusbar__counts" role="status" aria-live="polite">
        <span className="count count--attention">
          <span className="count__value">{attention}</span>
          <span className="label">Needs you</span>
        </span>
        <span className="count">
          <span className="count__value">{critical}</span>
          <span className="label">Critical</span>
        </span>
        <span className="count">
          <span className="count__value">{open}</span>
          <span className="label">Open</span>
        </span>
      </div>

      <nav className="statusbar__nav" aria-label="Views">
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          aria-current={view === 'queue'}
          onClick={() => onNavigate('queue')}
        >
          Queue
        </button>
        <button
          type="button"
          className="btn btn--primary btn--sm"
          onClick={() => onNavigate('intake')}
        >
          New report
        </button>
      </nav>
    </header>
  )
}
