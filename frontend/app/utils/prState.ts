/**
 * Utilities for PR state display
 */

type PRStateColor = 'success' | 'primary' | 'error'

/**
 * Get badge color for PR state
 */
export function getPRStateColor(state: string): PRStateColor {
  if (state === 'open' || state === 'opened') return 'success'
  if (state === 'merged') return 'primary'
  return 'error'
}

/**
 * Normalize PR state label (GitLab uses 'opened', GitHub uses 'open')
 */
export function getPRStateLabel(state: string): string {
  return state === 'opened' ? 'open' : state
}
