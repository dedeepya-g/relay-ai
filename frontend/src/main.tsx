import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'

import { CampusProvider } from './lib/CampusContext'
import { router } from './routes'
import './index.css'

const container = document.getElementById('root')
if (!container) {
  throw new Error('Root element #root is missing from index.html')
}

createRoot(container).render(
  <StrictMode>
    <CampusProvider>
      <RouterProvider router={router} />
    </CampusProvider>
  </StrictMode>,
)
