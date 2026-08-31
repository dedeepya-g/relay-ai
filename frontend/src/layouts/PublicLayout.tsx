/**
 * The public shell: everything a reporter or a first-time visitor sees.
 *
 * Deliberately lighter than the ops header -- no counters, no live data --
 * because nobody arriving here is on shift. The `marketing` class scopes the
 * display serif to this side of the site; it is never applied under `/ops`.
 */
import { useEffect } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'

/**
 * Scroll to a hash target after navigation.
 *
 * The router changes the url without moving the page, so an in-page link from
 * another route would otherwise land at the top with the fragment ignored.
 * Honours the same reduced-motion preference the rest of the site does.
 */
function useHashScroll() {
  const { hash, pathname } = useLocation()
  useEffect(() => {
    if (!hash) return
    const target = document.querySelector(hash)
    if (!target) return
    const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    // Deferred a frame so the target exists after a route change.
    const id = window.setTimeout(
      () => target.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'start' }),
      0,
    )
    return () => window.clearTimeout(id)
  }, [hash, pathname])
}

export function PublicLayout() {
  useHashScroll()
  return (
    <div className="marketing">
      <header className="publicbar">
        <Link to="/" className="publicbar__mark wordmark">
          Relay
        </Link>
        <nav className="publicbar__nav" aria-label="Site">
          <Link to="/#how-it-works" className="publicbar__link">
            How it works
          </Link>
          <NavLink to="/report" className="publicbar__link">
            Report an issue
          </NavLink>
          <Link to="/ops" className="btn btn--primary btn--sm">
            Ops dashboard
          </Link>
        </nav>
      </header>

      <Outlet />
    </div>
  )
}
