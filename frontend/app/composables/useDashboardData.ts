/**
 * Composable for managing dashboard data fetching
 * Handles loading organizations, repositories, and pull requests
 *
 * Uses useOrganizationSelection for org selection (store is source of truth)
 */

import type { DashboardStatsResponse, PullRequestListItem } from '@reviewate/api-types'
import { getDashboardStats } from '@reviewate/api-types'

import type { UIPullRequest } from '~/types/pullRequest'

/**
 * Filter options for pull requests
 */
export interface PullRequestFilters {
  state?: string // 'all' | 'open' | 'closed' | 'merged'
  dateFilter?: string // 'all' | 'today' | '7days' | '30days' | '90days'
  search?: string
  repositoryIds?: string[] // Multi-select repository filter
  author?: string[] // Filter by author username(s) ('mine' resolves to all provider usernames)
}

/**
 * Convert date filter string to Date object
 */
function getDateFromFilter(dateFilter: string): Date | undefined {
  if (dateFilter === 'all') return undefined

  const now = new Date()
  switch (dateFilter) {
    case 'today':
      return new Date(now.getFullYear(), now.getMonth(), now.getDate())
    case '7days':
      return new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
    case '30days':
      return new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
    case '90days':
      return new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000)
    default:
      return undefined
  }
}

export function useDashboardData() {
  const orgsStore = useOrganizationsStore()
  const reposStore = useRepositoriesStore()
  const pullRequestsStore = usePullRequestsStore()

  // Use the organization selection composable (store is source of truth)
  const { selectedOrgId, selectOrgById } = useOrganizationSelection()

  const isLoading = ref(false)
  const isFiltering = ref(false) // Separate loading state for filter changes
  const error = ref<string | null>(null)

  // Dashboard stats
  const stats = ref<DashboardStatsResponse | null>(null)
  const statsLoading = ref(false)

  // Current active filters
  const currentFilters = ref<PullRequestFilters>({
    state: 'open',
    dateFilter: '7days',
    search: '',
  })

  // Pagination state
  const currentPage = ref(1)
  const totalPullRequests = ref(0)

  /**
   * Fetch dashboard stats from the API
   */
  async function fetchStats() {
    statsLoading.value = true
    try {
      const { data } = await getDashboardStats()
      if (data) {
        stats.value = data
      }
    } catch (e) {
      console.error('[useDashboardData] Error fetching stats:', e)
    } finally {
      statsLoading.value = false
    }
  }

  /**
   * Fetch initial dashboard data
   * Loads organizations, repositories, and the first page of pull requests
   */
  async function fetchDashboardData(pageSize: number = 25, filters?: PullRequestFilters) {
    isLoading.value = true
    error.value = null

    // Update current filters if provided
    if (filters) {
      currentFilters.value = { ...currentFilters.value, ...filters }
    }

    try {
      // Fetch organizations
      const orgsSuccess = await orgsStore.fetchOrganizations()
      if (!orgsSuccess) {
        error.value = 'Failed to load organizations'
        return
      }

      // No organizations yet - this is not an error
      if (orgsStore.organizations.length === 0) {
        return
      }

      // Fetch repositories, pull requests, and stats in parallel
      await Promise.all([
        Promise.all(
          orgsStore.organizations.map((org) => reposStore.fetchRepositories(org.id)),
        ),
        fetchPullRequestsPage(1, pageSize, currentFilters.value),
        fetchStats(),
      ])
    } catch (e) {
      console.error('[useDashboardData] Error fetching dashboard data:', e)
      error.value = e instanceof Error ? e.message : 'Failed to load dashboard data'
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Refetch pull requests with new filters (keeps orgs/repos, just updates PRs)
   * Resets to page 1 when filters change
   */
  async function refetchWithFilters(filters: PullRequestFilters, pageSize: number = 25) {
    isFiltering.value = true
    currentFilters.value = { ...currentFilters.value, ...filters }
    currentPage.value = 1 // Reset to first page on filter change

    try {
      await fetchPullRequestsPage(1, pageSize, currentFilters.value)
    } catch (e) {
      console.error('[useDashboardData] Error refetching with filters:', e)
    } finally {
      isFiltering.value = false
    }
  }

  /**
   * Fetch a specific page of pull requests
   * @param page Page number (1-indexed)
   * @param pageSize Items per page
   * @param filters Optional filters
   */
  async function fetchPullRequestsPage(page: number, pageSize: number = 25, filters?: PullRequestFilters) {
    // Convert filters to API format, including organization filter
    const apiFilters = {
      state: filters?.state && filters.state !== 'all' ? filters.state : undefined,
      createdAfter: filters?.dateFilter ? getDateFromFilter(filters.dateFilter) : undefined,
      search: filters?.search || undefined,
      repositoryIds: filters?.repositoryIds?.length ? filters.repositoryIds : undefined,
      author: filters?.author?.length ? filters.author : undefined,
      // Include organization filter from selectedOrgId (server-side filtering)
      organizationId: selectedOrgId.value || undefined,
    }

    const result = await pullRequestsStore.fetchAllPullRequests(page, pageSize, false, apiFilters)

    if (result.success) {
      currentPage.value = page
      totalPullRequests.value = result.total
    } else {
      console.warn(`Failed to load page ${page}`)
    }

    return result
  }

  /**
   * Go to a specific page
   */
  async function goToPage(page: number, pageSize: number = 25) {
    isFiltering.value = true
    try {
      await fetchPullRequestsPage(page, pageSize, currentFilters.value)
    } finally {
      isFiltering.value = false
    }
  }

  /**
   * Set selected organization filter and reload data
   * This updates the store's selectedOrgId (single source of truth)
   */
  async function setSelectedOrg(orgId: string | null) {
    selectOrgById(orgId)
    // Clear existing PR data when switching orgs
    pullRequestsStore.$reset()
    await fetchDashboardData()
  }

  /**
   * Get pull requests with UI enhancements
   * Uses flat paginated list from server-side pagination
   */
  const pullRequests = computed<UIPullRequest[]>(() => {
    // Get paginated PRs from store (already filtered by backend, including org filter)
    const prs = pullRequestsStore.getAllPaginatedPullRequests()

    // Enhance API data with UI-specific fields
    return prs.map((pr: PullRequestListItem): UIPullRequest => {
      const executionDisplay = mapExecutionStatus(
        pr.latest_execution_status,
        pr.latest_execution_error_type,
        pr.latest_execution_error_detail,
      )
      // Get repo name from reposStore or use repository_id as fallback
      const repo = reposStore.getRepositoryById(pr.repository_id)

      return {
        ...pr, // Spread all API fields
        // Add UI-specific computed fields
        repository: repo?.name ?? 'Unknown',
        date: formatRelativeTime(pr.created_at),
        executionDisplay,
      }
    })
  })

  return {
    isLoading: readonly(isLoading),
    isFiltering: readonly(isFiltering),
    error: readonly(error),
    pullRequests,
    selectedOrgId,
    currentFilters,
    // Pagination state (from backend)
    totalPullRequests: readonly(totalPullRequests),
    currentPage: readonly(currentPage),
    // Dashboard stats
    stats: readonly(stats),
    statsLoading: readonly(statsLoading),
    // Actions
    fetchDashboardData,
    refetchWithFilters,
    goToPage,
    setSelectedOrg,
  }
}
