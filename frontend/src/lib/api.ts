/**
 * Typed client for the Relay backend.
 *
 * Every request goes through `request` so base URL handling and error
 * translation stay in one place. Errors carry the server's own message where
 * there is one, because the API writes messages a person can act on and
 * replacing them with "something went wrong" would throw that away.
 */
import type {
  Campus,
  IncidentDetail,
  IncidentStatus,
  IncidentSummary,
  OverdueSweepResult,
  PendingReview,
  ReportIntakeResult,
  StatusUpdateResult,
} from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8080'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/** True when the API could not be reached at all, as opposed to refusing. */
export class OfflineError extends Error {
  readonly baseUrl = API_BASE_URL
  constructor() {
    super(`Could not reach the Relay API at ${API_BASE_URL}`)
    this.name = 'OfflineError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init)
  } catch {
    throw new OfflineError()
  }

  if (!response.ok) {
    let detail = `Request to ${path} failed`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      /* Non-JSON error body; the default message stands. */
    }
    throw new ApiError(detail, response.status)
  }

  return (await response.json()) as T
}

export function getCampus(): Promise<Campus> {
  return request<Campus>('/campus')
}

export function listIncidents(): Promise<{ incidents: IncidentSummary[]; count: number }> {
  return request('/incidents')
}

export function getIncident(incidentId: string): Promise<IncidentDetail> {
  return request<IncidentDetail>(`/incidents/${incidentId}`)
}

export function listReviews(): Promise<{ reports: PendingReview[]; count: number }> {
  return request('/reviews')
}

export interface SubmitReportInput {
  description: string
  buildingId: string
  floor?: string
  room?: string
  photo?: File | null
}

export function submitReport(input: SubmitReportInput): Promise<ReportIntakeResult> {
  const body = new FormData()
  body.append('description', input.description)
  body.append('building_id', input.buildingId)
  if (input.floor) body.append('floor', input.floor)
  if (input.room) body.append('room', input.room)
  if (input.photo) body.append('photo', input.photo)
  return request<ReportIntakeResult>('/reports', { method: 'POST', body })
}

/**
 * Move an incident to a new lifecycle status.
 *
 * The server owns which transitions are legal and refuses the rest, so the UI
 * offering only the legal next steps is a convenience rather than the check.
 * A rejected transition arrives here as an `ApiError` carrying the server's
 * own explanation, which is written to be shown to a person.
 */
export function updateIncidentStatus(
  incidentId: string,
  newStatus: IncidentStatus,
  notes?: string,
): Promise<StatusUpdateResult> {
  const trimmed = notes?.trim()
  return request<StatusUpdateResult>(`/incidents/${incidentId}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_status: newStatus, notes: trimmed ? trimmed : null }),
  })
}

/** Run one pass of the overdue sweep, escalating anything past its deadline. */
export function checkOverdue(): Promise<OverdueSweepResult> {
  return request<OverdueSweepResult>('/admin/check-overdue', { method: 'POST' })
}

/**
 * Apply a reviewer's decision to a paused report.
 *
 * `note` is the reviewer's own reasoning and is recorded in the audit trail in
 * place of the default rationale. An empty note is sent as null rather than as
 * a filler string, so the trail reads as "no reason given" instead of
 * attributing words to a person who never wrote them.
 */
export function resolveReview(
  reportId: string,
  resolution: 'same_incident' | 'different_incident',
  incidentId?: string,
  note?: string,
): Promise<{ report_id: string; outcome: string; incident_id: string }> {
  const trimmed = note?.trim()
  return request(`/reports/${reportId}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      resolution,
      incident_id: incidentId ?? null,
      note: trimmed ? trimmed : null,
    }),
  })
}
