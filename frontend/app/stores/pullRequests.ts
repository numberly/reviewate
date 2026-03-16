/**
 * Pull Requests Store
 *
 * Manages pull request data for repositories.
 * Pull requests are fetched from the backend with their latest execution status.
 */
import {
  listAllPullRequests,
  triggerReview,
} from '@reviewate/api-types'
import type { PullRequestListItem } from '@reviewate/api-types'
import { defineStore } from 'pinia'

export const usePullRequestsStore = defineStore('pullRequests', () => {
  // ============================================================================
  // State
  // ============================================================================

  // Flat list for server-side pagination (used by fetchAllPullRequests)
  const paginatedPullRequests = ref<PullRequestListItem[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // ============================================================================
  // Getters
  // ============================================================================

  /**
   * Get all paginated pull requests (for server-side pagination)
   */
  function getAllPaginatedPullRequests(): PullRequestListItem[] {
    return paginatedPullRequests.value
  }

  // ============================================================================
  // Actions
  // ============================================================================

  const client = useApi()

  /**
   * Fetch all pull requests for the user across all organizations (single API call)
   * @param page Page number (1-indexed)
   * @param limit Items per page
   * @param append Whether to append results or replace existing data
   * @param filters Optional filters (state, date, search)
   * @returns Object with success status and pagination info
   */
  async function fetchAllPullRequests(
    page: number = 1,
    limit: number = 100,
    append: boolean = false,
    filters?: {
      state?: string
      createdAfter?: Date
      search?: string
      repositoryIds?: string[]
      author?: string[]
      organizationId?: string
    },
  ): Promise<{ success: boolean, hasMore: boolean, total: number }> {
    isLoading.value = true
    error.value = null

    try {
      const { data, error: apiError } = await listAllPullRequests({
        client,
        query: {
          page,
          limit,
          state: filters?.state && filters.state !== 'all' ? filters.state : undefined,
          created_after: filters?.createdAfter?.toISOString(),
          search: filters?.search || undefined,
          repository_ids: filters?.repositoryIds?.length ? filters.repositoryIds : undefined,
          author: filters?.author?.length ? filters.author : undefined,
          organization_id: filters?.organizationId || undefined,
        },
      })

      if (apiError) {
        console.error('[Pull Requests Store] Failed to fetch all pull requests:', apiError)
        error.value = 'Failed to load pull requests'
        return { success: false, hasMore: false, total: 0 }
      }

      const newPRs = data?.objects ?? []
      const total = data?.pagination?.total ?? 0
      const hasMore = page * limit < total

      // Store as flat list for server-side pagination
      if (append) {
        paginatedPullRequests.value = [...paginatedPullRequests.value, ...newPRs]
      } else {
        paginatedPullRequests.value = newPRs
      }

      return { success: true, hasMore, total }
    } catch (e) {
      console.error('[Pull Requests Store] Network error:', e)
      error.value = e instanceof Error ? e.message : 'Failed to load pull requests'
      return { success: false, hasMore: false, total: 0 }
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Trigger a code review for a specific pull request
   * @returns execution_id if trigger succeeded, null otherwise
   */
  async function triggerReviewForPR(prId: string, commitSha: string): Promise<string | null> {
    isLoading.value = true
    error.value = null

    try {
      const { data, error: apiError } = await triggerReview({
        client,
        path: {
          pr_id: prId,
        },
        body: {
          commit_sha: commitSha,
        },
      })

      if (apiError) {
        console.error('[Pull Requests Store] Failed to trigger review:', apiError)
        error.value = 'Failed to trigger review'
        return null
      }

      return data?.execution_id ?? null
    } catch (e) {
      console.error('[Pull Requests Store] Network error:', e)
      error.value = e instanceof Error ? e.message : 'Failed to trigger review'
      return null
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Update a PR's execution status in-place (for SSE real-time updates).
   * Returns true if the PR was found and updated, false if not on current page.
   */
  function updatePRExecutionStatus(
    prId: string,
    executionId: string,
    status: string,
    updatedAt: string,
    state?: string,
    errorType?: string | null,
    errorDetail?: string | null,
  ): boolean {
    const index = paginatedPullRequests.value.findIndex((pr) => pr.id === prId)
    if (index === -1) return false

    const existing = paginatedPullRequests.value[index]!
    // Clear error fields when status is not failed (e.g., retry transitions)
    const isFailed = status === 'failed'
    paginatedPullRequests.value[index] = {
      ...existing,
      latest_execution_id: executionId,
      latest_execution_status: status,
      updated_at: updatedAt,
      ...(state && { state }),
      latest_execution_error_type: isFailed ? (errorType ?? null) : null,
      latest_execution_error_detail: isFailed ? (errorDetail ?? null) : null,
    } as typeof existing
    return true
  }

  /**
   * Reset store to initial state
   */
  function $reset(): void {
    paginatedPullRequests.value = []
    isLoading.value = false
    error.value = null
  }

  return {
    // State
    paginatedPullRequests,
    isLoading,
    error,

    // Getters
    getAllPaginatedPullRequests,

    // Actions
    fetchAllPullRequests,
    triggerReviewForPR,
    updatePRExecutionStatus,
    $reset,
  }
})
