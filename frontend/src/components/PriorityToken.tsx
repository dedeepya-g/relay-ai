/**
 * Priority, encoded three ways.
 *
 * Colour alone would fail a colour-blind reader and fail anyone glancing at
 * this board across a room, so every token also carries an uppercase label and
 * a distinct shape: filled square, half-filled, hollow, dot.
 */
import type { Priority } from '../lib/types'

const LABELS: Record<Priority, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

export function PriorityToken({ priority }: { priority: Priority }) {
  return (
    <span className={`priority priority--${priority}`}>
      <span className="priority__token" aria-hidden="true" />
      {LABELS[priority]}
    </span>
  )
}
