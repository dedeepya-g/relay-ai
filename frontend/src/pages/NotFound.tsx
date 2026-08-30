/** Nothing at this address. */
import { Link } from 'react-router-dom'

export function NotFound() {
  return (
    <main className="shell">
      <div className="panel" style={{ marginTop: '3rem' }}>
        <div className="empty">
          <strong>There is nothing at this address.</strong>
          The page you asked for does not exist.
          <div className="review__actions" style={{ marginTop: '1.25rem', justifyContent: 'center' }}>
            <Link to="/" className="btn btn--sm">
              Back to the start
            </Link>
            <Link to="/ops" className="btn btn--sm">
              Ops dashboard
            </Link>
          </div>
        </div>
      </div>
    </main>
  )
}
