/**
 * Campus reference data, fetched once for the whole application.
 *
 * Lives above the routes rather than inside the ops shell because both sides
 * of the site need it: a reporter picks a building on `/report`, and the ops
 * board resolves building and team names from the same document. Fetching it
 * per route would load it twice and let the two drift within a session.
 */
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { getCampus } from './api'
import type { Campus } from './types'

interface CampusState {
  campus: Campus | null
  /** Why the layout is unavailable, when it is. Null while loading or on success. */
  error: string | null
  loading: boolean
}

const CampusContext = createContext<CampusState>({
  campus: null,
  error: null,
  loading: true,
})

export function CampusProvider({ children }: { children: ReactNode }) {
  const [campus, setCampus] = useState<Campus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const loaded = await getCampus()
        if (!cancelled) {
          setCampus(loaded)
          setError(null)
        }
      } catch (caught) {
        if (!cancelled) {
          setError(
            caught instanceof Error
              ? caught.message
              : 'Relay could not load the campus layout.',
          )
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const value = useMemo(
    () => ({ campus, error, loading }),
    [campus, error, loading],
  )
  return <CampusContext.Provider value={value}>{children}</CampusContext.Provider>
}

export function useCampus(): CampusState {
  return useContext(CampusContext)
}
