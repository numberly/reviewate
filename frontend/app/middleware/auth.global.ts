/**
 * Authentication Middleware
 *
 * Protects routes that require authentication.
 * Redirects to login page if user is not authenticated.
 * Redirects to home page if already authenticated and accessing login page.
 *
 * Works on both server and client:
 * - Server: Checks if session cookie exists (quick redirect if not)
 * - Client: Validates session with API call
 */
export default defineNuxtRouteMiddleware(async (to) => {
  const isLoginPage = to.path === '/login'

  // Check for session cookie (works on both server and client)
  const sessionCookie = useCookie('reviewate_session')
  const hasSessionCookie = !!sessionCookie.value

  // Server-side: Quick check based on cookie presence
  if (import.meta.server) {
    // No cookie = definitely not authenticated, redirect to login
    if (!isLoginPage && !hasSessionCookie) {
      return navigateTo('/login')
    }
    // Has cookie = might be authenticated, let client validate
    // Don't redirect authenticated users on server (let client handle)
    return
  }

  // Client-side: Full validation with API
  const authStore = useAuthStore()

  // If not initialized, fetch user from API
  if (!authStore.isInitialized) {
    await authStore.fetchUser()
  }

  const isAuthenticated = authStore.isAuthenticated

  // Redirect authenticated users away from login page
  if (isLoginPage && isAuthenticated) {
    return navigateTo('/')
  }

  // Redirect unauthenticated users to login
  if (!isLoginPage && !isAuthenticated) {
    return navigateTo('/login')
  }
})
