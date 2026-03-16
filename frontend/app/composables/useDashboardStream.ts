/**
 * Composable for global dashboard SSE stream
 * ONE connection for ALL PRs across all organizations
 * Uses the generic useSSE factory with callback pattern
 */

import { useSSE } from './useSSE'

export interface DashboardPRUpdateEvent {
  pull_request_id: string
  organization_id: string
  repository_id: string
  action: string
  state?: string
  latest_execution_id?: string
  latest_execution_status?: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'
  latest_execution_created_at?: string
  updated_at: string
  workflow?: 'review' | 'summarize'
  error_type?: string | null
  error_detail?: string | null
}

export function useDashboardStream() {
  // Callbacks registered by components
  const callbacks = new Set<(event: DashboardPRUpdateEvent) => void>()

  const handleEvent = (data: DashboardPRUpdateEvent) => {
    // Broadcast to all registered callbacks
    callbacks.forEach((callback) => {
      try {
        callback(data)
      } catch (e) {
        console.error('[Dashboard SSE] Callback error:', e)
      }
    })
  }

  const sse = useSSE<DashboardPRUpdateEvent>({
    urlPath: '/pull-requests/stream',
    eventName: 'pr_update',
    onEvent: handleEvent,
    useRefCounting: true,
    logPrefix: '[Dashboard SSE]',
  })

  function onPRUpdate(callback: (event: DashboardPRUpdateEvent) => void) {
    callbacks.add(callback)

    // Return cleanup function
    return () => {
      callbacks.delete(callback)
    }
  }

  return {
    ...sse,
    onPRUpdate,
  }
}
