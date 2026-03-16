/**
 * Organizations Store
 *
 * Manages organization/source data for the current user.
 * Organizations are connected via GitHub App installation or GitLab tokens.
 */
import {
  addGitlabSource as addGitlabSourceApi,
  deleteGitlabOrganization,
  getGithubInstallUrl,
  listSources,
  uninstallGithubApp,
} from '@reviewate/api-types'
import type { OrganizationListItem } from '@reviewate/api-types'
import { defineStore } from 'pinia'

export const useOrganizationsStore = defineStore('organizations', () => {
  // ============================================================================
  // State
  // ============================================================================

  const organizations = ref<OrganizationListItem[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const isInitialized = ref(false)

  // Selected organization ID (persists across navigation)
  const selectedOrgId = ref<string | null>(null)

  // GitLab API state (modal state moved to page component)
  const isAddingGitlab = ref(false)
  const gitlabError = ref<string | null>(null)

  // SSE connection
  let sseConnection: ReturnType<typeof useOrganizationSSE> | null = null

  // ============================================================================
  // Getters
  // ============================================================================

  /** Whether user has any organizations */
  const hasOrganizations = computed(() => organizations.value.length > 0)

  /** Currently selected organization */
  const selectedOrg = computed(() => {
    if (!selectedOrgId.value) return null
    return organizations.value.find((org) => org.id === selectedOrgId.value) ?? null
  })

  // ============================================================================
  // Actions
  // ============================================================================

  const client = useApi()

  /**
   * Handle SSE organization events
   */
  function handleOrganizationEvent(event: CustomEvent): void {
    const { action, organization } = event.detail

    switch (action) {
      case 'created':
      case 'updated': {
        // Update or add organization
        const existingIndex = organizations.value.findIndex((o) => o.id === organization.id)
        if (existingIndex >= 0) {
          organizations.value[existingIndex] = organization
        } else {
          organizations.value.push(organization)
        }
        break
      }
      case 'deleted': {
        // Remove organization
        organizations.value = organizations.value.filter((o) => o.id !== organization.id)
        break
      }
    }
  }

  /**
   * Start SSE connection for real-time organization updates
   */
  function startSSE(): void {
    if (sseConnection) return

    sseConnection = useOrganizationSSE()
    sseConnection.connect()

    // Listen for organization update events
    window.addEventListener('organization-update', handleOrganizationEvent as EventListener)
  }

  /**
   * Stop SSE connection
   */
  function stopSSE(): void {
    if (sseConnection) {
      sseConnection.disconnect()
      sseConnection = null
    }
    window.removeEventListener('organization-update', handleOrganizationEvent as EventListener)
  }

  /**
   * Fetch all organizations for the current user
   * @returns true if fetch succeeded, false otherwise
   */
  async function fetchOrganizations(): Promise<boolean> {
    isLoading.value = true
    error.value = null

    try {
      const { data, error: apiError } = await listSources({ client })

      if (apiError) {
        error.value = 'Failed to load organizations'
        return false
      }

      organizations.value = data?.objects ?? []

      // Start SSE after initial fetch
      if (!sseConnection) {
        startSSE()
      }

      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load organizations'
      return false
    } finally {
      isLoading.value = false
      isInitialized.value = true
    }
  }

  /**
   * Get GitHub App installation URL and redirect user
   * @returns true if installation URL was retrieved, false otherwise
   */
  async function installGitHubApp(): Promise<boolean> {
    try {
      // Fetch GitHub App installation URL from backend using typed API client
      const { data, error: apiError } = await getGithubInstallUrl()

      if (apiError || !data) {
        throw new Error('Failed to get GitHub App installation URL')
      }

      window.location.href = data.url
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to get GitHub App installation URL'
      return false
    }
  }

  /**
   * Add GitLab source using access token
   * @returns Object with success status and optional organization ID
   */
  async function addGitlabSource(accessToken: string, providerUrl: string = 'https://gitlab.com'): Promise<{ success: boolean, organizationId?: string }> {
    isAddingGitlab.value = true
    gitlabError.value = null

    try {
      const { data, error: apiError } = await addGitlabSourceApi({
        client,
        body: {
          access_token: accessToken,
          provider_url: providerUrl,
        },
      })

      if (apiError || !data) {
        // Extract error detail from API response if available
        const errorDetail = (apiError as { detail?: string })?.detail
        gitlabError.value = errorDetail || 'Failed to add GitLab source. Please check your token.'
        return { success: false }
      }

      // Refresh organizations list
      await fetchOrganizations()

      // Return the organization ID for repository refresh
      // For project tokens, we need to find the org by looking up the namespace
      // For group tokens, the source_id is the organization ID
      const organizationId = data.source_type === 'group' ? data.source_id : undefined

      return { success: true, organizationId }
    } catch (e) {
      gitlabError.value = e instanceof Error ? e.message : 'Failed to add GitLab source'
      return { success: false }
    } finally {
      isAddingGitlab.value = false
    }
  }

  /**
   * Set selected organization by ID
   */
  function setSelectedOrgId(id: string | null): void {
    selectedOrgId.value = id
  }

  /**
   * Delete an organization
   * Calls the appropriate provider-specific endpoint (GitHub or GitLab)
   * @returns true if deletion succeeded, false otherwise
   */
  async function deleteOrganization(orgId: string): Promise<boolean> {
    isLoading.value = true
    error.value = null

    try {
      // Find the organization to determine the provider
      const org = organizations.value.find((o) => o.id === orgId)
      if (!org) {
        error.value = 'Organization not found'
        return false
      }

      let apiError

      if (org.provider === 'github') {
        // For GitHub: uninstall the GitHub App (also deletes from DB)
        const result = await uninstallGithubApp({
          client,
          path: { org_id: orgId },
        })
        apiError = result.error
      } else if (org.provider === 'gitlab') {
        // For GitLab: delete the organization from our database
        const result = await deleteGitlabOrganization({
          client,
          path: { org_id: orgId },
        })
        apiError = result.error
      } else {
        error.value = `Unsupported provider: ${org.provider}`
        return false
      }

      if (apiError) {
        console.error('[Organizations Store] Failed to delete organization:', apiError)
        error.value = 'Failed to delete organization'
        return false
      }

      // Remove from local state
      organizations.value = organizations.value.filter((o) => o.id !== orgId)

      return true
    } catch (e) {
      console.error('[Organizations Store] Network error:', e)
      error.value = e instanceof Error ? e.message : 'Failed to delete organization'
      return false
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Reset store to initial state
   */
  function $reset(): void {
    stopSSE()
    organizations.value = []
    isLoading.value = false
    error.value = null
    isInitialized.value = false
    selectedOrgId.value = null
    isAddingGitlab.value = false
    gitlabError.value = null
  }

  return {
    // State
    organizations,
    isLoading,
    error,
    isInitialized,
    selectedOrgId,
    isAddingGitlab,
    gitlabError,

    // Getters
    hasOrganizations,
    selectedOrg,

    // Actions
    fetchOrganizations,
    installGitHubApp,
    addGitlabSource,
    setSelectedOrgId,
    deleteOrganization,
    startSSE,
    stopSSE,
    $reset,
  }
})
