/**
 * Repositories Store
 *
 * Manages repository data for organizations.
 * Repositories are added via GitHub/GitLab integration.
 */
import {
  deleteRepository as deleteRepositoryApi,
  listRepositories,
} from '@reviewate/api-types'
import type { RepositoryListItem } from '@reviewate/api-types'
import { defineStore } from 'pinia'

export const useRepositoriesStore = defineStore('repositories', () => {
  // ============================================================================
  // State
  // ============================================================================

  const repositories = ref<Map<string, RepositoryListItem[]>>(new Map())
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const isDeleting = ref(false)

  // SSE connections per organization
  const sseConnections = new Map<string, ReturnType<typeof useRepositorySSE>>()

  // ============================================================================
  // Getters
  // ============================================================================

  /**
   * Get repositories for a specific organization
   */
  function getRepositoriesByOrgId(orgId: string): RepositoryListItem[] {
    return repositories.value.get(orgId) ?? []
  }

  /**
   * Check if repositories are loaded for an organization
   */
  function isLoadedForOrg(orgId: string): boolean {
    return repositories.value.has(orgId)
  }

  /**
   * Get all repositories across all organizations
   */
  const allRepositories = computed(() => {
    const all: RepositoryListItem[] = []
    for (const repos of repositories.value.values()) {
      all.push(...repos)
    }
    return all
  })

  /**
   * Get a single repository by ID (searches all organizations)
   */
  function getRepositoryById(repoId: string): RepositoryListItem | undefined {
    for (const repos of repositories.value.values()) {
      const repo = repos.find((r) => r.id === repoId)
      if (repo) return repo
    }
    return undefined
  }

  // ============================================================================
  // Actions
  // ============================================================================

  const client = useApi()

  /**
   * Handle SSE repository events
   */
  function handleRepositoryEvent(event: CustomEvent): void {
    const { organization_id, action, repository } = event.detail

    const orgRepos = repositories.value.get(organization_id) ?? []

    switch (action) {
      case 'created':
      case 'updated': {
        // Update or add repository
        const existingIndex = orgRepos.findIndex((r) => r.id === repository.id)
        if (existingIndex >= 0) {
          orgRepos[existingIndex] = repository
        } else {
          orgRepos.push(repository)
        }
        repositories.value.set(organization_id, orgRepos)
        break
      }
      case 'deleted': {
        // Remove repository
        const filtered = orgRepos.filter((r) => r.id !== repository.id)
        repositories.value.set(organization_id, filtered)
        break
      }
    }
  }

  /**
   * Start SSE connection for an organization
   */
  function startSSE(orgId: string): void {
    if (sseConnections.has(orgId)) return

    const connection = useRepositorySSE(orgId)
    connection.connect()
    sseConnections.set(orgId, connection)

    // Listen for repository update events
    window.addEventListener('repository-update', handleRepositoryEvent as EventListener)
  }

  /**
   * Stop SSE connection for an organization
   */
  function stopSSE(orgId: string): void {
    const connection = sseConnections.get(orgId)
    if (connection) {
      connection.disconnect()
      sseConnections.delete(orgId)
    }

    // Only remove listener if no more connections
    if (sseConnections.size === 0) {
      window.removeEventListener('repository-update', handleRepositoryEvent as EventListener)
    }
  }

  /**
   * Fetch repositories for a specific organization
   * @returns true if fetch succeeded, false otherwise
   */
  async function fetchRepositories(orgId: string): Promise<boolean> {
    isLoading.value = true
    error.value = null

    try {
      const { data, error: apiError } = await listRepositories({
        client,
        path: {
          org_id: orgId,
        },
      })

      if (apiError) {
        console.error('[Repositories Store] Failed to fetch repositories:', apiError)
        error.value = 'Failed to load repositories'
        return false
      }

      // Store repositories for this organization
      repositories.value.set(orgId, data?.objects ?? [])

      // Start SSE after initial fetch
      if (!sseConnections.has(orgId)) {
        startSSE(orgId)
      }

      return true
    } catch (e) {
      console.error('[Repositories Store] Network error:', e)
      error.value = e instanceof Error ? e.message : 'Failed to load repositories'
      return false
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Delete a repository
   * @returns true if deletion succeeded, false otherwise
   */
  async function deleteRepository(repoId: string, orgId: string): Promise<boolean> {
    isDeleting.value = true
    error.value = null

    try {
      const { error: apiError } = await deleteRepositoryApi({
        client,
        path: {
          repo_id: repoId,
        },
      })

      if (apiError) {
        console.error('[Repositories Store] Failed to delete repository:', apiError)
        error.value = 'Failed to delete repository'
        return false
      }

      // Remove from local state
      const orgRepos = repositories.value.get(orgId)
      if (orgRepos) {
        const filtered = orgRepos.filter((repo) => repo.id !== repoId)
        repositories.value.set(orgId, filtered)
      }

      return true
    } catch (e) {
      console.error('[Repositories Store] Network error:', e)
      error.value = e instanceof Error ? e.message : 'Failed to delete repository'
      return false
    } finally {
      isDeleting.value = false
    }
  }

  /**
   * Reset store to initial state
   */
  function $reset(): void {
    // Stop all SSE connections
    for (const orgId of sseConnections.keys()) {
      stopSSE(orgId)
    }
    repositories.value.clear()
    isLoading.value = false
    error.value = null
    isDeleting.value = false
  }

  return {
    // State
    repositories,
    isLoading,
    error,
    isDeleting,

    // Getters
    getRepositoriesByOrgId,
    getRepositoryById,
    isLoadedForOrg,
    allRepositories,

    // Actions
    fetchRepositories,
    deleteRepository,
    startSSE,
    stopSSE,
    $reset,
  }
})
