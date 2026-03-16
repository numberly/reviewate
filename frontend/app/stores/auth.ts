/**
 * Authentication Store
 *
 * Manages user authentication state using SSO providers (GitHub, GitLab, Google).
 * Authentication is handled via backend OAuth flow with HTTP-only cookies.
 */
import { getMe, logout as logoutApi } from '@reviewate/api-types'
import type { UserProfile } from '@reviewate/api-types'
import { defineStore } from 'pinia'

/**
 * OAuth provider types supported by the application
 */
type OAuthProvider = 'github' | 'gitlab' | 'google'

export const useAuthStore = defineStore('auth', () => {
  // ============================================================================
  // State
  // ============================================================================

  const user = ref<UserProfile | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const isInitialized = ref(false)

  // ============================================================================
  // Getters
  // ============================================================================

  /** Whether user is currently authenticated */
  const isAuthenticated = computed(() => !!user.value)

  /** User's display name (username or email fallback) */
  const displayName = computed(
    () => user.value?.display_username || user.value?.email || '',
  )

  /** User's initials for avatar */
  const userInitials = computed(() => {
    if (!user.value) return ''
    const name = user.value.display_username || user.value.email || ''
    return name
      .split(/[@.\s]/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part: string) => part[0]?.toUpperCase())
      .join('')
  })

  /** Check if user has linked a specific provider */
  const hasLinkedProvider = (provider: OAuthProvider): boolean => {
    if (!user.value) return false
    switch (provider) {
      case 'github':
        return !!user.value.github_external_id
      case 'gitlab':
        return !!user.value.gitlab_external_id
      case 'google':
        return !!user.value.google_external_id
      default:
        return false
    }
  }

  // ============================================================================
  // Actions
  // ============================================================================

  const client = useApi()

  /**
   * Fetch current user profile from backend.
   * Called on app initialization to check auth status.
   * @returns true if user is authenticated, false otherwise
   */
  async function fetchUser(): Promise<boolean> {
    isLoading.value = true
    error.value = null

    try {
      const { data, error: apiError } = await getMe({ client })

      if (apiError) {
        // 401/403 means not authenticated - this is expected
        user.value = null
        return false
      }

      user.value = data ?? null
      return true
    } catch (e) {
      // Network error or other issue
      console.error('[Auth Store] Network error:', e)
      user.value = null
      return false
    } finally {
      isLoading.value = false
      isInitialized.value = true
    }
  }

  /**
   * Initiate OAuth login flow by redirecting to backend OAuth endpoint.
   * Backend handles OAuth dance and sets session cookie on callback.
   *
   * Uses a Nuxt server route (/api/auth/[provider]) as a proxy so that
   * the API base URL is read from environment variables at RUNTIME,
   * not baked into the client bundle at build time.
   *
   * @param provider - OAuth provider to use
   */
  function login(provider: OAuthProvider): void {
    // Use server route proxy - reads API URL from env vars at runtime
    window.location.href = `/api/auth/${provider}`
  }

  /**
   * Logout user by calling backend logout endpoint.
   * Backend clears the session cookie.
   * @returns true if logout succeeded, false otherwise
   */
  async function logout(): Promise<boolean> {
    isLoading.value = true
    error.value = null

    try {
      const { error: apiError } = await logoutApi({ client })

      if (apiError) {
        console.error('[Auth Store] Logout error:', apiError)
        error.value = 'Logout failed'
        return false
      }

      user.value = null
      isInitialized.value = false // Reset initialization state

      // Redirect to login page
      await navigateTo('/login')
      return true
    } catch (e) {
      console.error('[Auth Store] Logout error:', e)
      error.value = e instanceof Error ? e.message : 'Logout failed'
      return false
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Clear any error state
   */
  function clearError(): void {
    error.value = null
  }

  /**
   * Reset store to initial state
   */
  function $reset(): void {
    user.value = null
    isLoading.value = false
    error.value = null
    isInitialized.value = false
  }

  return {
    // State
    user,
    isLoading,
    error,
    isInitialized,

    // Getters
    isAuthenticated,
    displayName,
    userInitials,
    hasLinkedProvider,

    // Actions
    fetchUser,
    login,
    logout,
    clearError,
    $reset,
  }
})
