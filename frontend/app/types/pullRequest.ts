/**
 * UI-specific type extensions for pull requests
 * Base data comes from PullRequestListItem in @reviewate/api-types
 */

import type { PullRequestListItem } from '@reviewate/api-types'

/**
 * Execution status display info
 */
export interface ExecutionStatusDisplay {
  label: string
  color: 'neutral' | 'primary' | 'success' | 'error' | 'warning'
  icon?: string
  errorType?: string | null
  errorDetail?: string | null
}

/**
 * UI-enhanced pull request with computed display fields
 */
export interface UIPullRequest extends PullRequestListItem {
  // UI-specific computed fields
  repository: string // Repository name for display
  date: string // Formatted relative time
  executionDisplay: ExecutionStatusDisplay // Computed from latest_execution_status
}
