/**
 * Application shell.
 *
 * Intentionally minimal for now: it confirms the frontend can reach the
 * backend. The report intake form and incident dashboard land here next.
 */
import { useEffect, useState } from 'react'

import { checkHealth } from './lib/api'

type ConnectionState = 'checking' | 'connected' | 'unavailable'

export default function App() {
  const [connection, setConnection] = useState<ConnectionState>('checking')

  useEffect(() => {
    let active = true
    checkHealth()
      .then(() => {
        if (active) setConnection('connected')
      })
      .catch(() => {
        if (active) setConnection('unavailable')
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <main className="app">
      <header className="app__header">
        <h1>Relay</h1>
        <p>Campus facilities coordination for Relay University.</p>
      </header>
      <p className={`status status--${connection}`}>
        {connection === 'checking' && 'Connecting to the Relay API…'}
        {connection === 'connected' && 'Connected to the Relay API.'}
        {connection === 'unavailable' && 'Relay API unavailable.'}
      </p>
    </main>
  )
}
