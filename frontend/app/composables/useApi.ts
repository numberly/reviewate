import { client } from '@reviewate/api-types'

/**
 * Global API client instance configured for the application.
 * Uses session-based authentication with HTTP-only cookies.
 */
let isConfigured = false

export const useApi = () => {
  if (!isConfigured) {
    const config = useRuntimeConfig()

    // Configure the default client
    client.setConfig({
      baseUrl: config.public.apiBase,
      credentials: 'include', // Always include cookies for session management
    })

    isConfigured = true
  }

  return client
}
