/**
 * Composable for streaming organization updates via SSE
 * Uses the generic useSSE factory
 */

import type { OrganizationListItem } from '@reviewate/api-types'

import { createCustomEventDispatcher, useSSE } from './useSSE'

export interface OrganizationEvent {
  user_id: string
  action: 'created' | 'updated' | 'deleted'
  organization: OrganizationListItem
  timestamp: string
}

/** Custom event name for organization updates */
export const ORGANIZATION_UPDATE_EVENT = 'organization-update'

export function useOrganizationSSE() {
  const dispatchEvent = createCustomEventDispatcher<OrganizationEvent>(ORGANIZATION_UPDATE_EVENT)

  return useSSE<OrganizationEvent>({
    urlPath: '/organizations/stream',
    eventName: 'org_update',
    onEvent: dispatchEvent,
    logPrefix: '[SSE Organization]',
  })
}
