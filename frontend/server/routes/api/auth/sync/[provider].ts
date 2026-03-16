/**
 * OAuth Sync Redirect Proxy
 *
 * This server route reads the API base URL from environment variables at RUNTIME
 * (not build time) and redirects to the backend sync endpoint.
 *
 * This is necessary because Nuxt's runtimeConfig.public values are baked into
 * the client bundle at build time. By using a server route, we can read
 * environment variables at runtime, making the Docker image generic.
 */
export default defineEventHandler((event) => {
  const provider = getRouterParam(event, 'provider')

  // Validate provider
  const validProviders = ['github', 'gitlab']
  if (!provider || !validProviders.includes(provider)) {
    throw createError({
      statusCode: 400,
      statusMessage: `Invalid sync provider: ${provider}`,
    })
  }

  // Read API base URL from runtime config (reads env var at runtime on server)
  const config = useRuntimeConfig()
  const apiBase = config.public.apiBase

  // Redirect to backend sync endpoint
  const redirectUrl = `${apiBase}/auth/sync/${provider}`
  return sendRedirect(event, redirectUrl, 302)
})
