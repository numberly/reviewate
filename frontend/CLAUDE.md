# Frontend

Nuxt 4 frontend with Vue 3, Pinia, and Nuxt UI.

## Structure

- `app/pages/` - File-based routing
- `app/components/` - Vue components
- `app/composables/` - Reusable composition functions
- `app/stores/` - Pinia stores for global state
- `app/locales/` - i18n translations (en.json, fr.json)

## API Client

Uses `@reviewate/api-types` (generated from OpenAPI). Configure once with `useApi()`:

```ts
import { getMe } from '@reviewate/api-types'

const { data } = await getMe()
```

API types are auto-generated from backend. Run `make generate-types` after backend changes.

## Stores

Pinia stores in `app/stores/` manage global state:

- `auth.ts` - User authentication state
- `organizations.ts` - Organization list
- `repositories.ts` - Repository list
- `pullRequests.ts` - Pull request list

## SSE (Real-time Updates)

Use `useSSE` composable for Server-Sent Events:

```ts
const sse = useSSE<MyEvent>({
  urlPath: '/my-endpoint/stream',
  eventName: 'my_event',
  onEvent: (data) => store.handleUpdate(data),
})
sse.connect()
```

## Commands

- `pnpm dev` - Start dev server
- `pnpm build` - Build for production
- `pnpm test:run` - Run tests (vitest)
- `pnpm lint:fix` - Fix linting issues
