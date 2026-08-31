/**
 * The three counts, as filters, on the board they filter.
 *
 * These used to sit in the header, where they were visible from screens they
 * could not act on. Here each number is next to the rows it counts, and
 * clicking one narrows to exactly those; clicking it again clears.
 */
import { Link } from 'react-router-dom'

import type { QueueFilter } from './OpsNav'

const COUNTS: { key: QueueFilter; label: string }[] = [
  { key: 'attention', label: 'Needs you' },
  { key: 'critical', label: 'Critical' },
  { key: 'open', label: 'Open' },
]

interface QueueFiltersProps {
  active: QueueFilter | null
  attention: number
  critical: number
  open: number
}

export function QueueFilters({ active, attention, critical, open }: QueueFiltersProps) {
  const values: Record<QueueFilter, number> = { attention, critical, open }

  return (
    <div className="filters" role="group" aria-label="Filter the board">
      {COUNTS.map((count) => {
        const on = active === count.key
        return (
          <Link
            key={count.key}
            to={on ? '/ops' : `/ops?filter=${count.key}`}
            className={`filter${on ? ' filter--on' : ''}${
              count.key === 'attention' ? ' filter--attention' : ''
            }`}
            aria-pressed={on}
          >
            <span className="filter__value">{values[count.key]}</span>
            <span className="filter__label">{count.label}</span>
          </Link>
        )
      })}
    </div>
  )
}
