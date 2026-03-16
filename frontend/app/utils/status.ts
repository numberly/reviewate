/**
 * Status mapping utilities for pull requests
 */

import { ExecutionStatus } from '~/types/execution'
import type { ExecutionStatusDisplay } from '~/types/pullRequest'

/**
 * Maps execution status from API to display format
 * @param executionStatus - The execution status from the API
 * @param errorType - Optional error type (for failed executions)
 * @param errorDetail - Optional error detail (for failed executions, self-hosted only)
 * @returns ExecutionStatusDisplay with label, color, and optional icon/error info
 */
export function mapExecutionStatus(
  executionStatus: string | null | undefined,
  errorType?: string | null,
  errorDetail?: string | null,
): ExecutionStatusDisplay {
  if (!executionStatus) {
    return {
      label: 'No review yet',
      color: 'neutral',
    }
  }

  switch (executionStatus) {
    case ExecutionStatus.QUEUED:
      return {
        label: 'Queued',
        color: 'primary',
      }
    case ExecutionStatus.PROCESSING:
      return {
        label: 'Reviewing',
        color: 'primary',
      }
    case ExecutionStatus.COMPLETED:
      return {
        label: 'Completed',
        color: 'success',
      }
    case ExecutionStatus.FAILED:
      return {
        label: 'Failed',
        color: 'error',
        errorType,
        errorDetail,
      }
    case ExecutionStatus.CANCELLED:
      return {
        label: 'Cancelled',
        color: 'neutral',
      }
    default:
      return {
        label: 'Unknown',
        color: 'neutral',
      }
  }
}
