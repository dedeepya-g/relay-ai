/**
 * Priority, drawn rather than named.
 *
 * Three segments read by height and fill. Only critical takes colour, so a
 * board of routine work stays quiet and the one row that is not routine is
 * the only one showing red.
 *
 * The level is still carried three ways -- height, fill weight, and the
 * accessible name -- so it survives greyscale, colour blindness, and a
 * screen reader. What it no longer needs is the word beside it.
 */
import type { Priority } from '../lib/types'

const SPOKEN: Record<Priority, string> = {
  critical: 'Critical priority',
  high: 'High priority',
  medium: 'Medium priority',
  low: 'Low priority',
}

export function PriorityToken({ priority }: { priority: Priority }) {
  return (
    <span className={`pri pri--${priority}`} role="img" aria-label={SPOKEN[priority]}>
      <span />
      <span />
      <span />
    </span>
  )
}
