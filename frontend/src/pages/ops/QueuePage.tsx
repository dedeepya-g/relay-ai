/**
 * The queue: the main working view, at `/ops`.
 *
 * Search, sort, and the counter filter all live in the url, so a narrowed
 * board is a place rather than a mode -- shareable, and survivable by the
 * back button.
 */
import { useNavigate, useSearchParams } from 'react-router-dom'

import { ListControls } from '../../components/ListControls'
import { QueueFilters } from '../../components/QueueFilters'
import type { QueueFilter } from '../../components/OpsNav'
import { useOps } from '../../layouts/OpsLayout'
import { buildAttention, matchesQuery, sortIncidents, type SortKey } from '../../lib/format'
import { QueueView } from '../../views/QueueView'

function isFilter(value: string | null): value is QueueFilter {
  return value === 'attention' || value === 'critical' || value === 'open'
}

function isSort(value: string | null): value is SortKey {
  return value === 'priority' || value === 'newest' || value === 'oldest'
}

export function QueuePage() {
  const { incidents, reviews, campus, now, loading, onResolve, onCheckOverdue } = useOps()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()

  const raw = params.get('filter')
  const filter = isFilter(raw) ? raw : null
  const query = params.get('q') ?? ''
  const sort: SortKey = isSort(params.get('sort')) ? (params.get('sort') as SortKey) : 'priority'

  /** Write one control's value into the url, dropping it when it goes empty. */
  function setParam(key: string, value: string | null) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  if (loading) {
    return (
      <div className="rowlist">
        <div className="empty">
          <strong>Reading the board…</strong>
        </div>
      </div>
    )
  }

  // The counter filters narrow to what each counter counts. "Needs you" is the
  // attention band's own membership, so it is taken from the same function the
  // band renders from rather than re-derived.
  const flaggedIds = new Set(
    buildAttention(incidents, reviews, now).flatMap((item) =>
      item.incident ? [item.incident.incident_id] : [],
    ),
  )

  const byFilter = incidents.filter((incident) => {
    if (filter === 'critical') return incident.priority === 'critical'
    if (filter === 'attention') return flaggedIds.has(incident.incident_id)
    return true
  })

  const visible = sortIncidents(
    byFilter.filter((incident) => matchesQuery(incident, query)),
    sort,
    (incident) => incident.created_at,
  )

  // Reports awaiting review are not incidents: "Open" and "Critical" are
  // statements about incidents, so those filters drop them. A search does too,
  // since it searches incident fields.
  const visibleReviews =
    filter === 'critical' || filter === 'open' || query.trim() !== ''
      ? []
      : filter === 'attention'
        ? reviews
        : reviews

  const narrowed = filter !== null || query.trim() !== '' || sort !== 'priority'

  return (
    <>
      <QueueFilters
        active={filter}
        attention={flaggedIds.size + reviews.length}
        critical={incidents.filter((i) => i.priority === 'critical').length}
        open={incidents.length}
      />

      <ListControls
        query={query}
        onQuery={(value) => setParam('q', value)}
        sort={sort}
        onSort={(value) => setParam('sort', value === 'priority' ? null : value)}
        showing={visible.length}
        total={incidents.length}
      />

      <QueueView
        incidents={visible}
        reviews={visibleReviews}
        campus={campus}
        now={now}
        flat={narrowed}
        emptyNote={
          narrowed ? 'Nothing here matches the current search and filter.' : undefined
        }
        onOpen={(id) => navigate(`/ops/incidents/${id}`)}
        onResolve={onResolve}
        onCheckOverdue={onCheckOverdue}
      />
    </>
  )
}
