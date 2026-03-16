/**
 * Composable for streaming repository updates via SSE
 * Uses the generic useSSE factory
 */

import type { RepositoryListItem } from '@reviewate/api-types'

import { createCustomEventDispatcher, useSSE } from './useSSE'

export interface RepositoryEvent {
  organization_id: string
  action: 'created' | 'updated' | 'deleted'
  repository: RepositoryListItem
  timestamp: string
}

/** Custom event name for repository updates */
export const REPOSITORY_UPDATE_EVENT = 'repository-update'

export function useRepositorySSE(organizationId: string) {
  const dispatchEvent = createCustomEventDispatcher<RepositoryEvent>(REPOSITORY_UPDATE_EVENT)

  return useSSE<RepositoryEvent>({
    urlPath: `/organizations/${organizationId}/repositories/stream`,
    eventName: 'repo_update',
    onEvent: dispatchEvent,
    logPrefix: '[SSE Repository]',
  })
}
