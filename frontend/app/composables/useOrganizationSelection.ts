/**
 * Composable for managing organization and repository selection
 * Provides a clean API over the store's selection state
 *
 * Single source of truth: organizations store owns selectedOrgId
 */

import type { OrganizationListItem, RepositoryListItem } from '@reviewate/api-types'

export function useOrganizationSelection() {
  const orgsStore = useOrganizationsStore()
  const reposStore = useRepositoriesStore()

  // ============================================================================
  // Organization Selection (store is source of truth)
  // ============================================================================

  /** Current selected organization ID - wraps store state */
  const selectedOrgId = computed({
    get: () => orgsStore.selectedOrgId,
    set: (val) => orgsStore.setSelectedOrgId(val),
  })

  /** Current selected organization - uses store's computed */
  const selectedOrg = computed(() => orgsStore.selectedOrg)

  /**
   * Select an organization by object
   */
  function selectOrg(org: OrganizationListItem | null) {
    orgsStore.setSelectedOrgId(org?.id ?? null)
  }

  /**
   * Select an organization by ID
   */
  function selectOrgById(orgId: string | null) {
    orgsStore.setSelectedOrgId(orgId)
  }

  // Fetch repositories when organization changes
  watch(selectedOrgId, (orgId) => {
    if (orgId && !reposStore.isLoadedForOrg(orgId)) {
      reposStore.fetchRepositories(orgId)
    }
  }, { immediate: true })

  // ============================================================================
  // Repository Selection (local to composable instance)
  // ============================================================================

  const selectedRepoId = ref<string | null>(null)

  const selectedRepo = computed(() => {
    if (!selectedRepoId.value || !selectedOrgId.value) return null
    const repos = reposStore.getRepositoriesByOrgId(selectedOrgId.value)
    return repos.find((repo: RepositoryListItem) => repo.id === selectedRepoId.value) ?? null
  })

  const repositories = computed(() => {
    if (!selectedOrgId.value) return []
    return reposStore.getRepositoriesByOrgId(selectedOrgId.value)
  })

  /**
   * Select a repository
   */
  function selectRepo(repo: RepositoryListItem | null) {
    selectedRepoId.value = repo?.id ?? null
  }

  /**
   * Reset repository selection
   */
  function resetRepoSelection() {
    selectedRepoId.value = null
  }

  // Reset repo selection when org changes
  watch(selectedOrgId, () => {
    resetRepoSelection()
  })

  return {
    // Organization state (from store)
    selectedOrgId,
    selectedOrg,
    selectOrg,
    selectOrgById,

    // Repository state (local)
    selectedRepoId,
    selectedRepo,
    repositories,
    selectRepo,
  }
}
