/**
 * Config Store
 *
 * Manages application configuration state including provider availability.
 * Fetched once on app init to determine which features to show/hide.
 */
import { getAppConfig } from '@reviewate/api-types'
import type { AppConfig } from '@reviewate/api-types'
import { defineStore } from 'pinia'

export const useConfigStore = defineStore('config', () => {
  // ============================================================================
  // State
  // ============================================================================

  const config = ref<AppConfig | null>(null)
  const isLoading = ref(false)
  const isInitialized = ref(false)

  // ============================================================================
  // Getters
  // ============================================================================

  /** Whether GitHub integration is enabled */
  const isGitHubEnabled = computed(() => config.value?.providers.github_enabled ?? false)

  /** Whether GitLab integration is enabled */
  const isGitLabEnabled = computed(() => config.value?.providers.gitlab_enabled ?? false)

  /** Whether Google integration is enabled */
  const isGoogleEnabled = computed(() => config.value?.providers.google_enabled ?? false)

  /** GitLab instance URL from backend config */
  const gitLabUrl = computed(() => config.value?.providers.gitlab_url ?? 'https://gitlab.com')

  // ============================================================================
  // Actions
  // ============================================================================

  const client = useApi()

  /**
   * Fetch application configuration from backend.
   * Called once on app initialization.
   */
  async function fetchConfig(): Promise<void> {
    if (isInitialized.value) return

    isLoading.value = true

    try {
      const { data } = await getAppConfig({ client })
      if (data) {
        config.value = data
      }
    } catch (e) {
      console.error('[Config Store] Failed to fetch config:', e)
    } finally {
      isLoading.value = false
      isInitialized.value = true
    }
  }

  /**
   * Reset store to initial state
   */
  function $reset(): void {
    config.value = null
    isLoading.value = false
    isInitialized.value = false
  }

  return {
    // State
    config,
    isLoading,
    isInitialized,

    // Getters
    isGitHubEnabled,
    isGitLabEnabled,
    isGoogleEnabled,
    gitLabUrl,

    // Actions
    fetchConfig,
    $reset,
  }
})
