/**
 * Typed client for the Relay backend.
 *
 * Every request goes through `request` so base URL handling and error
 * translation stay in one place.
 */
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

export interface HealthResponse {
  status: string
  service: string
}

/** Issue a JSON request against the Relay API. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })

  if (!response.ok) {
    throw new ApiError(`Request to ${path} failed`, response.status)
  }

  return (await response.json()) as T
}

/** Verify the backend is reachable. */
export function checkHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/healthz')
}
