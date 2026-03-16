/**
 * Tests for usePullRequestFilters composable
 *
 * Note: Backend filtering is tested via API integration tests.
 * These tests verify the composable's URL state management and filter state.
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { computed, defineComponent } from 'vue'

import { usePullRequestFilters } from '~/composables/usePullRequestFilters'
import type { UIPullRequest } from '~/types/pullRequest'

// Mock vue-router
vi.mock('vue-router', () => ({
  useRoute: () => ({
    query: {},
  }),
  useRouter: () => ({
    replace: vi.fn(),
  }),
}))

// Mock VueUse
vi.mock('@vueuse/core', () => ({
  refDebounced: (ref: { value: string }) => ref,
  useLocalStorage: (_key: string, defaultValue: unknown) => ({ value: defaultValue }),
}))

/**
 * Run a composable inside a component setup context to avoid
 * "onMounted called without active component" warnings.
 */
function withSetup<T>(composableFn: () => T): T {
  let result!: T
  mount(defineComponent({
    setup() {
      result = composableFn()
      return {}
    },
    template: '<div />',
  }))
  return result
}

// Helper to create mock PRs
function createMockPR(overrides: Partial<UIPullRequest> = {}): UIPullRequest {
  return {
    id: 'pr-1',
    organization_id: 'org-1',
    repository_id: 'repo-1',
    pr_number: 1,
    external_pr_id: 'ext-1',
    title: 'Test PR',
    author: 'testuser',
    state: 'open',
    head_branch: 'feature',
    base_branch: 'main',
    head_sha: 'abc123',
    pr_url: 'https://github.com/org/repo/pull/1',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    author_reviewate_disabled: false,
    latest_execution_id: null,
    latest_execution_status: null,
    latest_execution_created_at: null,
    repository: 'test-repo',
    date: '1 hour ago',
    executionDisplay: { label: 'Pending', color: 'neutral', icon: 'i-heroicons-clock' },
    ...overrides,
  }
}

describe('usePullRequestFilters', () => {
  describe('default values', () => {
    it('should have default date filter of 7days', () => {
      const pullRequests = computed(() => [] as UIPullRequest[])
      const { dateFilter } = withSetup(() => usePullRequestFilters(pullRequests))

      expect(dateFilter.value).toBe('7days')
    })

    it('should have default status filter of open', () => {
      const pullRequests = computed(() => [] as UIPullRequest[])
      const { statusFilter } = withSetup(() => usePullRequestFilters(pullRequests))

      expect(statusFilter.value).toBe('open')
    })

    it('should have default author filter of mine', () => {
      const pullRequests = computed(() => [] as UIPullRequest[])
      const { authorFilter } = withSetup(() => usePullRequestFilters(pullRequests))

      expect(authorFilter.value).toBe('mine')
    })

    it('should have empty search query by default', () => {
      const pullRequests = computed(() => [] as UIPullRequest[])
      const { searchQuery } = withSetup(() => usePullRequestFilters(pullRequests))

      expect(searchQuery.value).toBe('')
    })
  })

  describe('filter options', () => {
    it('should provide status options', () => {
      const pullRequests = computed(() => [] as UIPullRequest[])
      const { statusOptions } = withSetup(() => usePullRequestFilters(pullRequests))

      expect(statusOptions.value).toHaveLength(4)
      expect(statusOptions.value.map((o) => o.value)).toEqual(['all', 'open', 'closed', 'merged'])
    })

    it('should provide date options', () => {
      const pullRequests = computed(() => [] as UIPullRequest[])
      const { dateOptions } = withSetup(() => usePullRequestFilters(pullRequests))

      expect(dateOptions.value).toHaveLength(5)
      expect(dateOptions.value.map((o) => o.value)).toEqual(['all', 'today', '7days', '30days', '90days'])
    })
  })

  describe('filteredPullRequests', () => {
    it('should pass through pull requests from backend (filtering done server-side)', () => {
      const mockPRs = [
        createMockPR({ id: 'pr-1', state: 'open' }),
        createMockPR({ id: 'pr-2', state: 'closed' }),
        createMockPR({ id: 'pr-3', state: 'merged' }),
      ]
      const pullRequests = computed(() => mockPRs)

      const { filteredPullRequests } = withSetup(() => usePullRequestFilters(pullRequests))

      // Backend filtering means all PRs pass through
      expect(filteredPullRequests.value).toHaveLength(3)
      expect(filteredPullRequests.value).toEqual(mockPRs)
    })
  })

  describe('refetchWithFilters callback', () => {
    it('should call refetchWithFilters when status filter changes', async () => {
      const pullRequests = computed(() => [] as UIPullRequest[])
      const mockRefetch = vi.fn().mockResolvedValue(undefined)

      const { statusFilter, applyFilters } = withSetup(() => usePullRequestFilters(pullRequests, mockRefetch))

      statusFilter.value = 'closed'
      await applyFilters()

      expect(mockRefetch).toHaveBeenCalledWith({
        state: 'closed',
        dateFilter: '7days',
        search: '',
        repositoryIds: undefined,
        author: undefined, // 'mine' but no user logged in = undefined
      })
    })

    it('should call refetchWithFilters when date filter changes', async () => {
      const pullRequests = computed(() => [] as UIPullRequest[])
      const mockRefetch = vi.fn().mockResolvedValue(undefined)

      const { dateFilter, applyFilters } = withSetup(() => usePullRequestFilters(pullRequests, mockRefetch))

      dateFilter.value = '30days'
      await applyFilters()

      expect(mockRefetch).toHaveBeenCalledWith({
        state: 'open',
        dateFilter: '30days',
        search: '',
        repositoryIds: undefined,
        author: undefined,
      })
    })

    it('should call refetchWithFilters when search changes', async () => {
      const pullRequests = computed(() => [] as UIPullRequest[])
      const mockRefetch = vi.fn().mockResolvedValue(undefined)

      const { searchQuery, applyFilters } = withSetup(() => usePullRequestFilters(pullRequests, mockRefetch))

      searchQuery.value = 'bug fix'
      await applyFilters()

      expect(mockRefetch).toHaveBeenCalledWith({
        state: 'open',
        dateFilter: '7days',
        search: 'bug fix',
        repositoryIds: undefined,
        author: undefined,
      })
    })

    it('should not fail if refetchWithFilters is not provided', async () => {
      const pullRequests = computed(() => [] as UIPullRequest[])

      const { applyFilters } = withSetup(() => usePullRequestFilters(pullRequests))

      // Should not throw
      await expect(applyFilters()).resolves.toBeUndefined()
    })
  })

  describe('pagination', () => {
    it('should start at page 1', () => {
      const pullRequests = computed(() => [] as UIPullRequest[])
      const { currentPage } = withSetup(() => usePullRequestFilters(pullRequests))

      expect(currentPage.value).toBe(1)
    })

    it('should have 10 items per page by default (SSR fallback)', () => {
      const pullRequests = computed(() => [] as UIPullRequest[])
      const { itemsPerPage } = withSetup(() => usePullRequestFilters(pullRequests))

      // In tests (simulating SSR), defaults to 10
      expect(itemsPerPage.value).toBe(10)
    })

    it('should provide page size options', () => {
      const pullRequests = computed(() => [] as UIPullRequest[])
      const { pageSizeOptions } = withSetup(() => usePullRequestFilters(pullRequests))

      expect(pageSizeOptions).toEqual([10, 25, 50])
    })
  })
})
