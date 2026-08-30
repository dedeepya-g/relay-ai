/**
 * The public report form, at `/report`.
 *
 * Owns its own submission state rather than reading the ops shell's, because
 * a reporter reaches this page without the dashboard around it and nothing
 * here should depend on the board being loaded.
 */
import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useCampus } from '../lib/CampusContext'
import { submitReport, type SubmitReportInput } from '../lib/api'
import { IntakeView } from '../views/IntakeView'
import type { ReportIntakeResult } from '../lib/types'

export function ReportPage() {
  const { campus, error: campusError } = useCampus()
  const navigate = useNavigate()
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<ReportIntakeResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = useCallback(async (input: SubmitReportInput) => {
    setSubmitting(true)
    setError(null)
    try {
      setResult(await submitReport(input))
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'Relay could not take that report. Try again.',
      )
    } finally {
      setSubmitting(false)
    }
  }, [])

  return (
    <main className="shell">
      <IntakeView
        campus={campus}
        campusError={campusError}
        submitting={submitting}
        result={result}
        error={error}
        onSubmit={handleSubmit}
        onOpenIncident={(id) => navigate(`/ops/incidents/${id}`)}
        onReset={() => {
          setResult(null)
          setError(null)
        }}
      />
    </main>
  )
}
