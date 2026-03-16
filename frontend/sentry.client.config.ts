import * as Sentry from '@sentry/nuxt'

const { public: { sentry } } = useRuntimeConfig()

if (sentry.dsn) {
  Sentry.init({
    dsn: sentry.dsn,
    tracesSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
    replaysSessionSampleRate: 0,
    integrations: [
      Sentry.replayIntegration(),
    ],
  })
}
