/**
 * One incident, at `/ops/incidents/:id`.
 *
 * Fetches its own detail from the url rather than receiving it from the queue,
 * which is what makes the address shareable: opening this link cold loads the
 * same screen as clicking through to it.
 */
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { useOps } from '../../layouts/OpsLayout'
import { getIncident } from '../../lib/api'
import { DetailView } from '../../views/DetailView'
import type { IncidentDetail, IncidentStatus } from '../../lib/types'

export function IncidentPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { campus, now, refresh, reportFailure, onChangeStatus } = useOps()
  const [detail, setDetail] = useState<IncidentDetail | null>(null)
  const [missing, setMissing] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!id) return
    try {
      setDetail(await getIncident(id))
      setMissing(null)
    } catch (caught) {
      setMissing(
        caught instanceof Error ? caught.message : `Could not open incident ${id}.`,
      )
      reportFailure(caught)
    }
  }, [id, reportFailure])

  useEffect(() => {
    setDetail(null)
    void load()
  }, [load])

  // Reload this incident before the board behind it: the status the reader
  // just changed should be correct on screen immediately.
  const handleChangeStatus = useCallback(
    async (incidentId: string, newStatus: IncidentStatus, notes?: string) => {
      await onChangeStatus(incidentId, newStatus, notes)
      await load()
    },
    [onChangeStatus, load],
  )

  if (missing) {
    return (
      <div className="rowlist">
        <div className="empty">
          <strong>That incident could not be opened.</strong>
          {missing}
        </div>
      </div>
    )
  }

  if (!detail) {
    return (
      <div className="rowlist">
        <div className="empty">
          <strong>Opening the incident…</strong>
        </div>
      </div>
    )
  }

  return (
    <DetailView
      detail={detail}
      campus={campus}
      now={now}
      onBack={() => {
        void refresh()
        navigate('/ops')
      }}
      onChangeStatus={handleChangeStatus}
    />
  )
}
