// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  modules: ['@nuxt/eslint', '@nuxt/ui', '@pinia/nuxt', '@nuxtjs/i18n', '@sentry/nuxt/module'],

  // Component configuration
  components: [
    {
      path: '~/components',
      pathPrefix: false,
    },
  ],

  // Auto-import configuration
  imports: {
    dirs: [
      'composables/**',
      'stores/**',
      'utils/**',
    ],
  },

  devtools: { enabled: true },

  // App configuration
  app: {
    head: {
      title: 'Reviewate',
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'description', content: 'AI-powered code review system' },
      ],
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/logo.svg' },
      ],
    },
  },

  // Global CSS
  css: ['~/assets/main.css'],

  // Runtime configuration
  runtimeConfig: {
    // Private keys (only available server-side)
    // Add server-side secrets here when needed

    // Public keys (exposed to the client)
    // Nuxt automatically overrides these with NUXT_PUBLIC_API_BASE and NUXT_PUBLIC_API_OPEN_API_URL
    public: {
      apiBase: 'http://localhost:8000',
      apiOpenApiUrl: 'http://localhost:8000/openapi.json',
      sentry: {
        dsn: '',
      },
    },
  },

  compatibilityDate: '2025-07-15',

  // TypeScript configuration
  typescript: {
    strict: true,
    typeCheck: process.env.NODE_ENV !== 'production', // Disable in production builds
    shim: false,
  },

  // ESLint configuration
  eslint: {
    config: {
      stylistic: true,
    },
  },

  // i18n configuration
  i18n: {
    locales: [
      { code: 'en', name: 'English', file: 'en.json' },
      { code: 'fr', name: 'Français', file: 'fr.json' },
    ],
    defaultLocale: 'en',
    langDir: '../app/locales',
    strategy: 'no_prefix',
    detectBrowserLanguage: {
      useCookie: true,
      cookieKey: 'i18n_redirected',
      fallbackLocale: 'en',
    },
  },

  // Pinia store configuration
  pinia: {
    storesDirs: ['./app/stores/**'],
  },
})
