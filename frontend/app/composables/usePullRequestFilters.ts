/**
 * Composable for managing pull request filters with backend filtering
 *
 * Features:
 * - Debounced search input (300ms)
 * - URL state persistence
 * - Stale-while-revalidate pattern (shows previous results while loading)
 * - Auto-fit page size based on viewport with user override
 */

import { refDebounced, useLocalStorage } from '@vueuse/core'

import type { UIPullRequest } from '~/types/pullRequest'

// Page size options for the selector
const PAGE_SIZE_OPTIONS = [10, 25, 50] as const

// Calculate optimal page size based on available viewport height
function calculateAutoPageSize(): number {
  if (import.meta.server) return 10 // SSR fallback

  // Estimate: header ~220px, filters ~50px, pagination footer ~50px, some padding
  const availableHeight = window.innerHeight - 320
  const rowHeight = 45 // Approximate row height in px

  const calculated = Math.floor(availableHeight / rowHeight)

  // Clamp to nearest option: 10, 25, or 50
  if (calculated >= 40) return 50
  if (calculated >= 18) return 25
  return 10
}

interface PaginationOptions {
  total: Ref<number>
  currentPage: Ref<number>
  goToPage: (page: number, pageSize: number) => Promise<void>
}

export function usePullRequestFilters(
  pullRequests: ComputedRef<UIPullRequest[]>,
  refetchWithFilters?: (filters: { state?: string, dateFilter?: string, search?: string, repositoryIds?: string[], author?: string[] }) => Promise<void>,
  pagination?: PaginationOptions,
) {
  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()
  const reposStore = useRepositoriesStore()
  const authStore = useAuthStore()

  // ============================================================================
  // Filter State (synced with URL)
  // ============================================================================

  const searchQuery = ref((route.query.search as string) || '')
  const statusFilter = ref((route.query.status as string) || 'open')
  const dateFilter = ref((route.query.date as string) || '7days')

  // Parse repository IDs from URL (comma-separated)
  const repoIdsFromUrl = (route.query.repos as string)?.split(',').filter(Boolean) || []
  const selectedRepositoryIds = ref<string[]>(repoIdsFromUrl)

  // Author filter: 'all' shows all PRs, 'mine' shows only current user's PRs
  // Default to 'mine' to show user's own PRs first
  const authorFilter = ref<'all' | 'mine'>((route.query.author as 'all' | 'mine') || 'mine')

  // Debounced search value for API calls
  const debouncedSearch = refDebounced(searchQuery, 300)

  const statusOptions = computed(() => [
    { label: t('filters.allStatuses'), value: 'all' },
    { label: 'Open', value: 'open' },
    { label: 'Closed', value: 'closed' },
    { label: 'Merged', value: 'merged' },
  ])

  const dateOptions = computed(() => [
    { label: t('filters.allTime'), value: 'all' },
    { label: t('filters.today'), value: 'today' },
    { label: t('filters.last7Days'), value: '7days' },
    { label: t('filters.last30Days'), value: '30days' },
    { label: t('filters.last90Days'), value: '90days' },
  ])

  // Repository options from store (all repos user has access to)
  const repositoryOptions = computed(() => {
    return reposStore.allRepositories.map((repo) => ({
      label: repo.name,
      value: repo.id,
    }))
  })

  // Get current user's provider usernames for "My PRs" filter
  // Returns all available usernames across providers (GitHub and GitLab may differ)
  const currentUserUsernames = computed(() => {
    const user = authStore.user
    if (!user) return []
    const usernames: string[] = []
    if (user.github_username) usernames.push(user.github_username)
    if (user.gitlab_username && user.gitlab_username !== user.github_username) usernames.push(user.gitlab_username)
    return usernames
  })

  // ============================================================================
  // URL State Sync
  // ============================================================================

  // Update URL when filters change (without navigation)
  function updateUrlState() {
    const query: Record<string, string> = {}
    if (statusFilter.value !== 'open') query.status = statusFilter.value
    if (dateFilter.value !== '7days') query.date = dateFilter.value
    if (searchQuery.value) query.search = searchQuery.value
    if (selectedRepositoryIds.value.length) query.repos = selectedRepositoryIds.value.join(',')
    if (authorFilter.value !== 'mine') query.author = authorFilter.value

    router.replace({ query })
  }

  // ============================================================================
  // Backend Filter Calls
  // ============================================================================

  // Call backend when filters change
  async function applyFilters() {
    if (refetchWithFilters) {
      // Convert 'mine' to actual usernames for API call (may have different usernames per provider)
      const authorUsernames = authorFilter.value === 'mine' ? currentUserUsernames.value : undefined
      await refetchWithFilters({
        state: statusFilter.value,
        dateFilter: dateFilter.value,
        search: debouncedSearch.value,
        repositoryIds: selectedRepositoryIds.value.length ? selectedRepositoryIds.value : undefined,
        author: authorUsernames?.length ? authorUsernames : undefined,
      })
    }
    updateUrlState()
  }

  // Watch for filter changes and refetch
  watch([statusFilter, dateFilter, selectedRepositoryIds, authorFilter], () => {
    applyFilters()
  }, { deep: true })

  // Watch debounced search separately
  watch(debouncedSearch, () => {
    applyFilters()
  })

  // ============================================================================
  // Filtered Results (passthrough - filtering done on backend)
  // ============================================================================

  // Results come pre-filtered from backend, just pass through
  // This enables stale-while-revalidate: old results show while new ones load
  const filteredPullRequests = computed(() => pullRequests.value)

  // ============================================================================
  // Pagination (server-side)
  // ============================================================================

  // Local page state (synced with server via pagination options)
  const localCurrentPage = ref(1)

  // Use server page if available, otherwise local
  const currentPage = computed({
    get: () => pagination?.currentPage.value ?? localCurrentPage.value,
    set: (val) => {
      localCurrentPage.value = val
    },
  })

  // Total items from server
  const totalItems = computed(() => pagination?.total.value ?? pullRequests.value.length)

  // Auto-calculate default, but respect user's stored preference
  const storedPageSize = useLocalStorage<number | null>('pr-list-page-size', null)
  const autoPageSize = ref(10) // Will be calculated on mount

  // Initialize auto page size on client
  onMounted(() => {
    autoPageSize.value = calculateAutoPageSize()
  })

  // Effective page size: user preference > auto-calculated
  // Coerce to number to handle localStorage returning strings
  const itemsPerPage = computed(() => {
    const stored = storedPageSize.value
    return stored !== null ? Number(stored) : autoPageSize.value
  })

  // Set page size (user override) - triggers server refetch
  async function setItemsPerPage(size: number) {
    storedPageSize.value = size
    localCurrentPage.value = 1
    // Refetch with new page size
    if (pagination?.goToPage) {
      await pagination.goToPage(1, size)
    }
  }

  // Handle page change - fetch from server
  async function setCurrentPage(page: number) {
    localCurrentPage.value = page
    if (pagination?.goToPage) {
      await pagination.goToPage(page, itemsPerPage.value)
    }
  }

  // Reset page when filters change (handled by refetchWithFilters resetting to page 1)
  watch([statusFilter, debouncedSearch, dateFilter, authorFilter], () => {
    localCurrentPage.value = 1
  })

  return {
    // Filter state
    searchQuery,
    statusFilter,
    dateFilter,
    selectedRepositoryIds,
    authorFilter,
    statusOptions,
    dateOptions,
    repositoryOptions,

    // Filtered data (from backend)
    filteredPullRequests,

    // Pagination (server-side)
    currentPage,
    totalItems,
    itemsPerPage,
    pageSizeOptions: PAGE_SIZE_OPTIONS,
    setItemsPerPage,
    setCurrentPage,

    // Actions
    applyFilters,
  }
}
