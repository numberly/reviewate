<script setup lang="ts">
import type { UIPullRequest } from '~/types/pullRequest'

const { t } = useI18n()
const orgsStore = useOrganizationsStore()

// Page metadata
useHead({
  title: () => `${t('dashboard.title')} - Reviewate`,
  meta: [
    { name: 'description', content: 'Premium AI-powered code review dashboard' },
  ],
})

// ============================================================================
// Dashboard Data
// ============================================================================

const {
  isLoading: _isLoading,
  isFiltering,
  error,
  pullRequests,
  fetchDashboardData,
  refetchWithFilters,
  goToPage,
  setSelectedOrg,
  currentFilters,
  totalPullRequests,
  currentPage: serverCurrentPage,
  stats,
  statsLoading,
} = useDashboardData()

// Show skeletons until data is initialized (skip during tour — demo data is ready)
const showSkeleton = computed(() => !orgsStore.isInitialized && !isTourActive.value)

// Handle organization selection for filtering
function handleOrgSelect(orgId: string | null) {
  setSelectedOrg(orgId)
  // Reset to page 1 when switching organizations
  currentPage.value = 1
}

// ============================================================================
// Pull Request Filters
// ============================================================================

const {
  searchQuery,
  statusFilter,
  dateFilter,
  selectedRepositoryIds: _selectedRepositoryIds,
  authorFilter,
  statusOptions,
  dateOptions,
  repositoryOptions: _repositoryOptions,
  filteredPullRequests,
  currentPage,
  totalItems,
  itemsPerPage,
  pageSizeOptions,
  setItemsPerPage,
  setCurrentPage,
} = usePullRequestFilters(pullRequests, refetchWithFilters, {
  total: totalPullRequests,
  currentPage: serverCurrentPage,
  goToPage,
})

// ============================================================================
// Review Actions
// ============================================================================

const pullRequestsStore = usePullRequestsStore()

async function handleReview(pr: UIPullRequest) {
  // During the tour, don't trigger real API calls
  if (isTourActive.value || pr.id.startsWith('demo-')) return

  const executionId = await pullRequestsStore.triggerReviewForPR(pr.id, pr.head_sha)

  if (!executionId) {
    console.error('[Dashboard] Failed to trigger review')
  }
  // SSE updates will be handled by the global dashboard stream
}

// ============================================================================
// Global Dashboard SSE Stream - Track updates instead of auto-applying
// ============================================================================

const dashboardStream = useDashboardStream()
const pendingUpdates = ref(0)
const isRefreshing = ref(false)

// Register callback for PR updates - update in-place or show refresh badge
const cleanupSSE = dashboardStream.onPRUpdate((event) => {
  // PR lifecycle events (created, state change, title change) → show refresh badge
  // A full refetch is needed to keep pagination/sorting/filtering consistent
  if (event.action === 'created' || event.action === 'updated') {
    pendingUpdates.value++
    return
  }

  // Ignore non-review workflows (e.g., summaries) — they shouldn't affect dashboard status
  if (event.workflow && event.workflow !== 'review') {
    return
  }

  // Execution events → try to update the PR in-place (status changes for visible PRs)
  const updated = pullRequestsStore.updatePRExecutionStatus(
    event.pull_request_id,
    event.latest_execution_id ?? '',
    event.latest_execution_status ?? '',
    event.updated_at,
    event.state,
    event.error_type,
    event.error_detail,
  )

  // PR not on current page → show refresh badge
  if (!updated) {
    pendingUpdates.value++
  }
})

// Refresh and clear pending updates
async function refreshPullRequests() {
  if (isRefreshing.value) return
  isRefreshing.value = true
  pendingUpdates.value = 0

  // Minimum delay for better UX feedback (prevents jarring instant updates)
  const minDelay = new Promise((resolve) => setTimeout(resolve, 400))
  // Spread to convert readonly to mutable
  await Promise.all([
    minDelay,
    refetchWithFilters({ ...currentFilters.value }, itemsPerPage.value),
  ])

  isRefreshing.value = false
}

// ============================================================================
// Lifecycle
// ============================================================================

const { startTour, resumeTour, shouldAutoStart, hasPendingStep, isTourActive, demoPullRequests, demoOrganizations } = useTour()

onMounted(async () => {
  // Fetch dashboard data with initial filters from URL/defaults
  // This ensures the author filter ('mine' by default) is applied on first load
  const authStore = useAuthStore()
  const usernames = [authStore.user?.github_username, authStore.user?.gitlab_username].filter((u): u is string => !!u)
  const initialAuthor = authorFilter.value === 'mine' && usernames.length
    ? usernames
    : undefined

  // Use the computed itemsPerPage for initial fetch (respects user's stored preference)
  await fetchDashboardData(itemsPerPage.value, {
    state: statusFilter.value,
    dateFilter: dateFilter.value,
    search: searchQuery.value,
    author: initialAuthor,
  })

  // Start SINGLE global SSE stream for all PRs
  dashboardStream.connect()

  // Start or resume onboarding tour
  if (hasPendingStep()) {
    setTimeout(() => resumeTour(), 300)
  } else if (shouldAutoStart()) {
    setTimeout(() => startTour(), 500)
  }
})

onUnmounted(() => {
  // Cleanup SSE callback and disconnect
  cleanupSSE()
  dashboardStream.disconnect()
})

// ============================================================================
// Organizations Data
// ============================================================================

const organizations = computed(() => isTourActive.value ? demoOrganizations : orgsStore.organizations)
const displayedPullRequests = computed(() => isTourActive.value ? demoPullRequests.value : filteredPullRequests.value)
const displayedTotalItems = computed(() => isTourActive.value ? demoPullRequests.value.length : totalItems.value)
</script>

<template>
  <!-- Header Section -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 pb-6 border-b border-neutral-200 dark:border-neutral-700 shrink-0">
    <div class="flex flex-col gap-0.5 relative z-10">
      <p class="text-xl sm:text-2xl font-semibold text-neutral-900 dark:text-neutral-100 tracking-tight">
        {{ $t('dashboard.title') }}
      </p>
      <p class="text-sm text-neutral-500 dark:text-neutral-400">
        {{ $t('dashboard.welcome') }}
      </p>
    </div>
  </div>

  <!-- Error Alert -->
  <UAlert
    v-if="error"
    color="error"
    variant="soft"
    :title="$t('common.error')"
    :description="error"
    class="mb-4"
    icon="i-lucide-alert-circle"
  />

  <!-- Stats Cards Row -->
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6 relative z-10 mb-4 sm:mb-6">
    <template v-if="statsLoading && !stats">
      <div
        v-for="i in 3"
        :key="i"
        class="h-28 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 animate-pulse"
      />
    </template>
    <template v-else>
      <StatsCard
        :label="$t('stats.activeRepos')"
        :value="String(stats?.active_repos ?? 0)"
        :change="formatChange(stats?.active_repos_change?.percentage, $t('stats.vsLastWeek'))"
        :trend="stats?.active_repos_change?.trend"
        icon="i-lucide-git-pull-request"
        icon-color="brand"
      />
      <StatsCard
        :label="$t('stats.avgReviewTime')"
        :value="formatDuration(stats?.avg_review_time_seconds)"
        :change="formatChange(stats?.avg_review_time_change?.percentage, $t('stats.vsLastWeek'))"
        :trend="stats?.avg_review_time_change?.trend"
        icon="i-lucide-clock"
        icon-color="warning"
      />
      <StatsCard
        :label="$t('stats.prsReviewedThisWeek')"
        :value="String(stats?.prs_reviewed ?? 0)"
        :change="formatChange(stats?.prs_reviewed_change?.percentage, $t('stats.vsLastWeek'))"
        :trend="stats?.prs_reviewed_change?.trend"
        icon="i-lucide-check-circle"
        icon-color="success"
      />
    </template>
  </div>

  <!-- Main Content: Organizations + PR Table -->
  <div class="flex flex-col lg:flex-row gap-4 sm:gap-6 relative z-10 lg:h-[calc(100vh-320px)] lg:min-h-[400px] min-w-0">
    <!-- Left column: Organizations (narrower) -->
    <div class="lg:w-64 xl:w-72 lg:flex-shrink-0 flex flex-col lg:min-h-0 lg:overflow-hidden">
      <!-- Organizations Skeleton -->
      <div
        v-if="showSkeleton"
        class="flex-1 rounded-lg border border-neutral-200 dark:border-neutral-700 p-3 space-y-2"
      >
        <div class="h-4 w-24 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
        <div class="space-y-1.5">
          <div class="h-9 bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
          <div class="h-9 bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
          <div class="h-9 bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
        </div>
      </div>
      <OrganizationsCard
        v-else
        :organizations="organizations"
        class="flex-1"
        @select-org="handleOrgSelect"
      />
    </div>

    <!-- Pull Requests Section - takes remaining space -->
    <div class="flex-1 flex flex-col lg:min-h-0 lg:overflow-hidden min-w-0">
      <!-- PR Header with Filters -->
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3 shrink-0">
        <div class="flex items-center gap-3 shrink-0">
          <h3 class="text-sm sm:text-base font-semibold text-neutral-900 dark:text-neutral-100 whitespace-nowrap">
            {{ $t('pullRequests.title') }}
          </h3>
          <!-- Switch: My PRs / All PRs -->
          <div
            id="tour-pr-switch"
            class="flex items-center gap-2"
          >
            <span
              class="text-xs font-medium transition-colors"
              :class="authorFilter === 'mine' ? 'text-neutral-900 dark:text-neutral-100' : 'text-neutral-400 dark:text-neutral-500'"
            >
              {{ $t('filters.myPRs') }}
            </span>
            <USwitch
              :model-value="authorFilter === 'all'"
              size="xs"
              @update:model-value="authorFilter = $event ? 'all' : 'mine'"
            />
            <span
              class="text-xs font-medium transition-colors"
              :class="authorFilter === 'all' ? 'text-neutral-900 dark:text-neutral-100' : 'text-neutral-400 dark:text-neutral-500'"
            >
              {{ $t('filters.allPRs') }}
            </span>
          </div>
          <!-- Refresh button with pending updates badge -->
          <UButton
            :color="pendingUpdates > 0 ? 'primary' : 'neutral'"
            :variant="pendingUpdates > 0 ? 'soft' : 'ghost'"
            size="xs"
            :disabled="isRefreshing"
            class="transition-all duration-300"
            :class="{ 'opacity-80': isRefreshing }"
            @click="refreshPullRequests"
          >
            <UIcon
              name="i-lucide-refresh-cw"
              class="w-3.5 h-3.5 transition-transform duration-300"
              :class="{ 'refresh-spin': isRefreshing }"
            />
            <span
              v-if="pendingUpdates > 0"
              class="transition-opacity duration-200"
            >
              {{ pendingUpdates }} {{ pendingUpdates === 1 ? 'update' : 'updates' }}
            </span>
          </UButton>
        </div>
        <div class="flex items-center gap-2 min-w-0">
          <UInput
            v-model="searchQuery"
            icon="i-heroicons-magnifying-glass"
            :placeholder="$t('pullRequests.searchPlaceholder')"
            size="sm"
            class="min-w-0 w-48 shrink"
          />
          <USelect
            v-model="statusFilter"
            :items="statusOptions"
            value-key="value"
            class="min-w-0 w-32 shrink"
            size="sm"
          />
          <USelect
            v-model="dateFilter"
            :items="dateOptions"
            value-key="value"
            class="min-w-0 w-36 shrink"
            size="sm"
          />
        </div>
      </div>

      <!-- PR List Skeleton -->
      <div
        v-if="showSkeleton"
        class="flex-1 space-y-3"
      >
        <div
          v-for="i in 5"
          :key="i"
          class="h-16 bg-neutral-100 dark:bg-neutral-800 rounded-lg animate-pulse"
        />
      </div>
      <!-- PR List (Desktop Table + Mobile Cards) -->
      <div
        v-else
        class="flex-1 flex flex-col lg:min-h-0 lg:overflow-hidden transition-opacity duration-200 ease-out"
        :class="{ 'opacity-50 pointer-events-none': isFiltering }"
      >
        <PullRequestList
          :current-page="currentPage"
          :pull-requests="displayedPullRequests"
          :items-per-page="itemsPerPage"
          :total-items="displayedTotalItems"
          :page-size-options="pageSizeOptions"
          @update:current-page="setCurrentPage"
          @update:items-per-page="setItemsPerPage"
          @review="handleReview"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.refresh-spin {
  animation: refresh-rotate 0.8s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}

@keyframes refresh-rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
