/**
 * Search and ordering for a list of incidents.
 *
 * Purely client-side: both boards already hold every row they display, so
 * narrowing them is a matter of not drawing some of them rather than asking
 * the server again.
 */
import type { SortKey } from '../lib/format'
import { SORT_LABELS } from '../lib/format'

interface ListControlsProps {
  query: string
  onQuery: (value: string) => void
  sort: SortKey
  onSort: (value: SortKey) => void
  /** Rows currently shown, and the total before narrowing. */
  showing: number
  total: number
  placeholder?: string
}

const SORTS: SortKey[] = ['priority', 'newest', 'oldest']

export function ListControls({
  query,
  onQuery,
  sort,
  onSort,
  showing,
  total,
  placeholder = 'Search titles, categories, teams, ids…',
}: ListControlsProps) {
  return (
    <div className="controls">
      <input
        type="search"
        className="input controls__search"
        value={query}
        placeholder={placeholder}
        aria-label="Search incidents"
        onChange={(event) => onQuery(event.target.value)}
      />

      <label className="controls__sort">
        <span className="label">Sort</span>
        <select
          className="select"
          value={sort}
          aria-label="Sort incidents"
          onChange={(event) => onSort(event.target.value as SortKey)}
        >
          {SORTS.map((key) => (
            <option key={key} value={key}>
              {SORT_LABELS[key]}
            </option>
          ))}
        </select>
      </label>

      {showing !== total && (
        <span className="label controls__count">
          {showing} of {total}
        </span>
      )}
    </div>
  )
}
