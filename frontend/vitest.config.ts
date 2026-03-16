import { defineVitestConfig } from '@nuxt/test-utils/config'

export default defineVitestConfig({
  test: {
    environment: 'nuxt',
    environmentOptions: {
      nuxt: {
        domEnvironment: 'happy-dom',
        overrides: {
          runtimeConfig: {
            public: {
              apiBase: 'http://localhost:8000',
              apiOpenApiUrl: 'http://localhost:8000/openapi.json',
            },
          },
        },
      },
    },
    include: ['app/**/*.{test,spec}.{js,ts,vue}'],
    globals: true,
    setupFiles: ['./app/tests/setup.ts'],
    // Suppress stderr output for expected warnings
    silent: false,
    // Reporter configuration
    reporters: ['default'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['app/components/**/*.vue'],
      exclude: ['node_modules', '.nuxt', '.output'],
    },
  },
})
