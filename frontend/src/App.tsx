/**
 * Application shell: data loading, view selection, and the shared clock.
 *
 * One clock ticks for the whole board. SLA counters, "due soon" flags, and the
 * attention band all read from it, so nothing drifts out of step with anything
 * else on screen.
 */
import { useCallback, useEffect, useState } from 'react'

import { StatusBar } from './components/StatusBar'
import { DetailView } from './views/DetailView'
import { IntakeView } from './views/IntakeView'
import { QueueView } from './views/QueueView'
import {
  getCampus,
  getIncident,
  listIncidents,
  listReviews,
  OfflineError,
  resolveReview,
  submitReport,
  type SubmitReportInput,
} from './lib/api'
import type {
  Campus,
  IncidentDetail,
  IncidentSummary,
  PendingReview,
  ReportIntakeResult,
} from './lib/types'

type View = 'queue' | 'intake' | 'detail'

const CLOCK_INTERVAL_MS = 1000
const POLL_INTERVAL_MS = 15000

export default function App() {
  const [view, setView] = useState<View>('queue')
  const [campus, setCampus] = useState<Campus | null>(null)
  const [incidents, setIncidents] = useState<IncidentSummary[]>([])
  const [reviews, setReviews] = useState<PendingReview[]>([])
  const [detail, setDetail] = useState<IncidentDetail | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const [loading, setLoading] = useState(true)
  const [offline, setOffline] = useState<OfflineError | null>(null)

  const [submitting, setSubmitting] = useState(false)
  const [intakeResult, setIntakeResult] = useState<ReportIntakeResult | null>(null)
  const [intakeError, setIntakeError] = useState<string | null>(null)

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), CLOCK_INTERVAL_MS)
    return () => window.clearInterval(id)
  }, [])

  const refresh = useCallback(async () => {
    try {
      const [incidentPage, reviewPage] = await Promise.all([listIncidents(), listReviews()])
      setIncidents(incidentPage.incidents)
      setReviews(reviewPage.reports)
      setOffline(null)
    } catch (caught) {
      if (caught instanceof OfflineError) setOffline(caught)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void (async () => {
      try {
        setCampus(await getCampus())
      } catch (caught) {
        if (caught instanceof OfflineError) setOffline(caught)
      }
      await refresh()
    })()
  }, [refresh])

  useEffect(() => {
    const id = window.setInterval(() => void refresh(), POLL_INTERVAL_MS)
    return () => window.clearInterval(id)
  }, [refresh])

  const openIncident = useCallback(async (incidentId: string) => {
    setView('detail')
    setDetail(null)
    try {
      setDetail(await getIncident(incidentId))
    } catch (caught) {
      if (caught instanceof OfflineError) setOffline(caught)
    }
  }, [])

  const handleSubmit = useCallback(
    async (input: SubmitReportInput) => {
      setSubmitting(true)
      setIntakeError(null)
      try {
        setIntakeResult(await submitReport(input))
        await refresh()
      } catch (caught) {
        setIntakeError(
          caught instanceof Error
            ? caught.message
            : 'Relay could not take that report. Try again.',
        )
      } finally {
        setSubmitting(false)
      }
    },
    [refresh],
  )

  const handleResolve = useCallback(
    async (
      reportId: string,
      resolution: 'same_incident' | 'different_incident',
      incidentId?: string,
    ) => {
      await resolveReview(reportId, resolution, incidentId)
      await refresh()
    },
    [refresh],
  )

  const attentionCount =
    reviews.length +
    incidents.filter((incident) => {
      if (!incident.sla_due_at) return false
      return new Date(incident.sla_due_at).getTime() - now <= 60_000
    }).length
  const criticalCount = incidents.filter((item) => item.priority === 'critical').length

  return (
    <>
      <StatusBar
        campusName={campus?.name ?? null}
        attention={attentionCount}
        open={incidents.length}
        critical={criticalCount}
        view={view === 'detail' ? 'queue' : view}
        onNavigate={(next) => {
          setView(next)
          if (next === 'intake') {
            setIntakeResult(null)
            setIntakeError(null)
          }
        }}
      />

      <main className="shell">
        {offline && (
          <p className="notice" style={{ marginBottom: '1.25rem' }}>
            <strong>Can’t reach the Relay API at {offline.baseUrl}.</strong>{' '}
            Start it with <code>uvicorn main:app --port 8080</code> from the{' '}
            <code>backend</code> directory, then this page will pick up on its own.
          </p>
        )}

        {view === 'intake' && (
          <IntakeView
            campus={campus}
            submitting={submitting}
            result={intakeResult}
            error={intakeError}
            onSubmit={handleSubmit}
            onOpenIncident={(id) => void openIncident(id)}
            onReset={() => {
              setIntakeResult(null)
              setIntakeError(null)
            }}
          />
        )}

        {view === 'queue' &&
          (loading ? (
            <div className="panel">
              <div className="empty">
                <strong>Reading the board…</strong>
              </div>
            </div>
          ) : (
            <QueueView
              incidents={incidents}
              reviews={reviews}
              campus={campus}
              now={now}
              onOpen={(id) => void openIncident(id)}
              onResolve={handleResolve}
            />
          ))}

        {view === 'detail' &&
          (detail ? (
            <DetailView
              detail={detail}
              campus={campus}
              now={now}
              onBack={() => {
                setView('queue')
                void refresh()
              }}
            />
          ) : (
            <div className="panel">
              <div className="empty">
                <strong>Opening the incident…</strong>
              </div>
            </div>
          ))}
      </main>
    </>
  )
}
