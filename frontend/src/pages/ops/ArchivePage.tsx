/**
 * Finished work, at `/ops/archive`.
 *
 * Fetches independently of the shell's poll. The queue refreshes every fifteen
 * seconds because live work changes underneath a reader; closed work does not,
 * so re-fetching it on a timer would spend requests to redraw the same rows.
 *
 * Deliberately quieter than the queue: no SLA countdown, no attention band,
 * no escalation flag. A deadline on finished work is not a thing to act on,
 * and showing one would invite a reader to treat the archive as a worklist.
 */
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { ListControls } from '../../components/ListControls'
import { CategoryGlyph } from '../../components/CategoryGlyph'
import { ClearBoard } from '../../components/ClearBoard'
import { useOps } from '../../layouts/OpsLayout'
import { listIncidents } from '../../lib/api'
import {
  formatAge,
  matchesQuery,
  sortIncidents,
  statusLabel,
  type SortKey,
} from '../../lib/format'
import type { IncidentSummary } from '../../lib/types'

export function ArchivePage() {
  const { now, reportFailure } = useOps()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [incidents, setIncidents] = useState<IncidentSummary[] | null>(null)

  const query = params.get('q') ?? ''
  const sortParam = params.get('sort')
  const sort: SortKey =
    sortParam === 'priority' || sortParam === 'oldest' ? sortParam : 'newest'

  function setParam(key: string, value: string | null) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  /** When the work actually finished, which is what the archive sorts on. */
  const finishedAt = (incident: IncidentSummary) =>
    incident.closed_at ?? incident.resolved_at ?? incident.updated_at

  const load = useCallback(async () => {
    try {
      const page = await listIncidents('archived')
      setIncidents(page.incidents)
    } catch (caught) {
      setIncidents([])
      reportFailure(caught)
    }
  }, [reportFailure])

  useEffect(() => {
    void load()
  }, [load])

  const resolved = incidents?.filter((i) => i.status === 'resolved').length ?? 0
  const closed = incidents?.filter((i) => i.status === 'closed').length ?? 0

  const visible = sortIncidents(
    (incidents ?? []).filter((incident) => matchesQuery(incident, query)),
    sort,
    finishedAt,
  )

  return (
    <>
      <div className="section-head">
        <h2 className="panel__title">Archive</h2>
        {incidents !== null && (
          <span className="label">
            {resolved} resolved · {closed} closed
          </span>
        )}
      </div>

      <ListControls
        query={query}
        onQuery={(value) => setParam('q', value)}
        sort={sort}
        onSort={(value) => setParam('sort', value === 'newest' ? null : value)}
        showing={visible.length}
        total={incidents?.length ?? 0}
        placeholder="Search finished work…"
      />

      <div className="panel">
        {incidents === null ? (
          <div className="empty">
            <strong>Reading the archive…</strong>
          </div>
        ) : visible.length === 0 ? (
          <div className="empty empty--art">
            <ClearBoard />
            <strong>
              {incidents.length === 0
                ? 'Nothing has been finished yet.'
                : 'Nothing matches that search.'}
            </strong>
            {incidents.length === 0
              ? 'Incidents appear here once they are resolved or closed. Until then they stay on the queue.'
              : `${incidents.length} finished ${incidents.length === 1 ? 'incident' : 'incidents'} are archived.`}
          </div>
        ) : (
          visible.map((incident) => (
            <button
              type="button"
              className="row row--archive"
              key={incident.incident_id}
              onClick={() => navigate(`/ops/incidents/${incident.incident_id}`)}
            >
              {/* Three things. Finished work is looked up, not scanned, so the
                  row carries what identifies it and when it ended -- the rest
                  is one click away and has room there. */}
              <CategoryGlyph category={incident.category} labelled />

              <span className="row__main">
                <span className="row__title">{incident.title}</span>
                <span className="row__peek">{incident.summary}</span>
              </span>

              <span className="glyph row__finished">
                {statusLabel(incident.status).toLowerCase()}{' '}
                {formatAge(
                  incident.closed_at ?? incident.resolved_at ?? incident.updated_at,
                  now,
                )}
              </span>
            </button>
          ))
        )}
      </div>
    </>
  )
}
