/**
 * The operations shell: navigation, live counters, and the data every ops
 * screen reads from.
 *
 * One clock ticks for the whole board and one poll feeds every page beneath
 * it. SLA counters, "due soon" flags, and the attention band all read from
 * that clock, so nothing drifts out of step with anything else on screen --
 * and a page does not restart the poll simply because it was navigated to.
 */
import { useCallback, useEffect, useState } from 'react'
import { Outlet, useOutletContext } from 'react-router-dom'

import { OpsNav } from '../components/OpsNav'
import { useCampus } from '../lib/CampusContext'
import {
  checkOverdue,
  listIncidents,
  listReviews,
  OfflineError,
  resolveReview,
  updateIncidentStatus,
} from '../lib/api'
import type {
  Campus,
  IncidentStatus,
  IncidentSummary,
  OverdueSweepResult,
  PendingReview,
} from '../lib/types'

const CLOCK_INTERVAL_MS = 1000
const POLL_INTERVAL_MS = 15000

/** What every ops page receives from the shell. */
export interface OpsContext {
  campus: Campus | null
  incidents: IncidentSummary[]
  reviews: PendingReview[]
  now: number
  loading: boolean
  refresh: () => Promise<void>
  reportFailure: (caught: unknown) => void
  onResolve: (
    reportId: string,
    resolution: 'same_incident' | 'different_incident',
    incidentId?: string,
    note?: string,
  ) => Promise<void>
  onChangeStatus: (
    incidentId: string,
    newStatus: IncidentStatus,
    notes?: string,
  ) => Promise<void>
  onCheckOverdue: () => Promise<OverdueSweepResult>
}

/** Typed accessor so a page never has to restate the context shape. */
export function useOps(): OpsContext {
  return useOutletContext<OpsContext>()
}

export function OpsLayout() {
  const { campus, error: campusError } = useCampus()
  const [incidents, setIncidents] = useState<IncidentSummary[]>([])
  const [reviews, setReviews] = useState<PendingReview[]>([])
  const [now, setNow] = useState(() => Date.now())
  const [loading, setLoading] = useState(true)
  const [offline, setOffline] = useState<OfflineError | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), CLOCK_INTERVAL_MS)
    return () => window.clearInterval(id)
  }, [])

  /**
   * Route a thrown value to the banner that describes it.
   *
   * Anything that is not an `OfflineError` reached the server and came back
   * with an explanation, so that explanation is shown rather than swallowed.
   */
  const reportFailure = useCallback((caught: unknown) => {
    if (caught instanceof OfflineError) {
      setOffline(caught)
      setApiError(null)
      return
    }
    setOffline(null)
    setApiError(caught instanceof Error ? caught.message : 'Relay returned an error.')
  }, [])

  const refresh = useCallback(async () => {
    try {
      const [incidentPage, reviewPage] = await Promise.all([
        listIncidents(),
        listReviews(),
      ])
      setIncidents(incidentPage.incidents)
      setReviews(reviewPage.reports)
      setOffline(null)
      setApiError(null)
    } catch (caught) {
      reportFailure(caught)
    } finally {
      setLoading(false)
    }
  }, [reportFailure])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    const id = window.setInterval(() => void refresh(), POLL_INTERVAL_MS)
    return () => window.clearInterval(id)
  }, [refresh])

  const onResolve = useCallback<OpsContext['onResolve']>(
    async (reportId, resolution, incidentId, note) => {
      await resolveReview(reportId, resolution, incidentId, note)
      await refresh()
    },
    [refresh],
  )

  const onChangeStatus = useCallback<OpsContext['onChangeStatus']>(
    async (incidentId, newStatus, notes) => {
      await updateIncidentStatus(incidentId, newStatus, notes)
      await refresh()
    },
    [refresh],
  )

  const onCheckOverdue = useCallback(async () => {
    const result = await checkOverdue()
    await refresh()
    return result
  }, [refresh])

  const context: OpsContext = {
    campus,
    incidents,
    reviews,
    now,
    loading,
    refresh,
    reportFailure,
    onResolve,
    onChangeStatus,
    onCheckOverdue,
  }

  return (
    <>
      <OpsNav />

      <main className="shell">
        {offline && (
          <p className="notice" style={{ marginBottom: '1.25rem' }}>
            <strong>No response from the Relay API at {offline.baseUrl}.</strong>{' '}
            Start it with <code>uvicorn main:app --port 8080</code> from the{' '}
            <code>backend</code> directory, then this page will pick up on its own.
          </p>
        )}

        {/* The server answered, so it is running: repeating the start-it advice
            here would send a reader to fix something that is not broken. */}
        {apiError && (
          <p className="notice" style={{ marginBottom: '1.25rem' }}>
            <strong>Relay is running but returned an error.</strong> {apiError}
          </p>
        )}

        {campusError && !apiError && !offline && (
          <p className="notice" style={{ marginBottom: '1.25rem' }}>
            <strong>Relay could not load the campus layout.</strong> Building and
            team names will show as ids. {campusError}
          </p>
        )}

        <Outlet context={context} />
      </main>
    </>
  )
}
