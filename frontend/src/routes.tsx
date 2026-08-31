/**
 * The route table: the single place that says what exists at what address.
 *
 * Two shells rather than one. The public side has no live data and no
 * counters; the ops side polls, holds a shared clock, and wraps every screen
 * in the same header. Keeping them separate means a reporter never pays for
 * the board's polling, and the display serif stays scoped to the public side.
 */
import { createBrowserRouter, Navigate } from 'react-router-dom'

import { OpsLayout } from './layouts/OpsLayout'
import { PublicLayout } from './layouts/PublicLayout'
import { Landing } from './pages/Landing'
import { NotFound } from './pages/NotFound'
import { ReportPage } from './pages/ReportPage'
import { ArchivePage } from './pages/ops/ArchivePage'
import { CampusPage } from './pages/ops/CampusPage'
import { IncidentPage } from './pages/ops/IncidentPage'
import { QueuePage } from './pages/ops/QueuePage'

export const router = createBrowserRouter([
  {
    element: <PublicLayout />,
    children: [
      { path: '/', element: <Landing /> },
      { path: '/report', element: <ReportPage /> },
      { path: '*', element: <NotFound /> },
    ],
  },
  {
    path: '/ops',
    element: <OpsLayout />,
    children: [
      { index: true, element: <QueuePage /> },
      { path: 'incidents/:id', element: <IncidentPage /> },
      { path: 'archive', element: <ArchivePage /> },
      { path: 'campus', element: <CampusPage /> },
      // Older links pointed at the queue as a view name rather than a path.
      { path: 'queue', element: <Navigate to="/ops" replace /> },
    ],
  },
])
