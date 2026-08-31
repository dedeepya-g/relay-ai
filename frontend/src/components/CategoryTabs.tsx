/**
 * Category tabs, generated from what is actually in the data.
 *
 * Nothing here is hardcoded: the tabs are the categories present in the rows
 * being shown, so a campus that never files a pest report never sees a Pest
 * tab, and a category added to the backend enum appears without a frontend
 * change.
 *
 * Counts follow the current search rather than the whole archive, so a tab
 * says how many matches are behind it rather than how many rows exist. That
 * makes the tab strip a map of where a search landed.
 *
 * Active state is the same underline the navigation uses, so "this is on"
 * means one thing everywhere.
 */
import { categoryLabel } from '../lib/format'
import type { IncidentSummary } from '../lib/types'

interface CategoryTabsProps {
  /** Rows after search, before the category filter. */
  incidents: IncidentSummary[]
  active: string | null
  onSelect: (category: string | null) => void
}

export function CategoryTabs({ incidents, active, onSelect }: CategoryTabsProps) {
  const counts = new Map<string, number>()
  for (const incident of incidents) {
    counts.set(incident.category, (counts.get(incident.category) ?? 0) + 1)
  }

  // Busiest first, alphabetical within a tie: the archive is browsed rather
  // than memorised, so leading with volume is more use than a fixed order.
  const categories = [...counts.entries()].sort(
    (a, b) => b[1] - a[1] || categoryLabel(a[0]).localeCompare(categoryLabel(b[0])),
  )

  if (categories.length < 2) return null

  return (
    <div className="tabs" role="tablist" aria-label="Filter by category">
      <button
        type="button"
        role="tab"
        aria-selected={active === null}
        className={`tab${active === null ? ' tab--on' : ''}`}
        onClick={() => onSelect(null)}
      >
        All <span className="tab__n">{incidents.length}</span>
      </button>

      {categories.map(([category, count]) => (
        <button
          key={category}
          type="button"
          role="tab"
          aria-selected={active === category}
          className={`tab${active === category ? ' tab--on' : ''}`}
          onClick={() => onSelect(active === category ? null : category)}
        >
          {categoryLabel(category)} <span className="tab__n">{count}</span>
        </button>
      ))}
    </div>
  )
}
