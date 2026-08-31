/**
 * The picture of a clear board.
 *
 * A plumb-line at rest: string, bob, and the level it settles to. It is the
 * oldest instrument in the trade and it means one thing, which is that
 * nothing is out of true. Drawn rather than written because "nothing needs
 * you" deserves a moment of calm rather than another sentence.
 *
 * One stroke weight in `--line`, with the bob and the level in `--ink` so the
 * eye lands on the thing that is settled.
 */
export function ClearBoard() {
  return (
    <svg
      className="clearboard"
      viewBox="0 0 120 96"
      width="120"
      height="96"
      fill="none"
      role="img"
      aria-label="A plumb line at rest"
    >
      {/* The beam it hangs from */}
      <path d="M18 14h84" stroke="var(--line)" strokeWidth="1.5" strokeLinecap="round" />
      {/* String */}
      <path d="M60 14v46" stroke="var(--line)" strokeWidth="1.5" strokeLinecap="round" />
      {/* Bob */}
      <path
        d="M60 60l5 8-5 9-5-9 5-8Z"
        stroke="var(--ink)"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      {/* The level it comes to rest against */}
      <path d="M24 88h72" stroke="var(--ink)" strokeWidth="1.5" strokeLinecap="round" />
      {/* Settled, and true */}
      <path d="M52 88h16" stroke="var(--line)" strokeWidth="4" strokeLinecap="round" />
    </svg>
  )
}
