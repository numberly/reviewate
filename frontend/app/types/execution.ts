/**
 * Execution status enum - matches backend ExecutionStatus
 * Keep in sync with backend/api/models/executions.py::ExecutionStatus
 */
export enum ExecutionStatus {
  QUEUED = 'queued',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

/**
 * Type guard to check if a string is a valid ExecutionStatus
 */
export function isExecutionStatus(value: string): value is ExecutionStatus {
  return Object.values(ExecutionStatus).includes(value as ExecutionStatus)
}
