# Reviewate Frontend

Nuxt 4 frontend for the Reviewate AI-powered code review system.

## Setup

1. Install dependencies:

```bash
pnpm install
```

2. Copy environment variables:

```bash
cp .env.example .env
```

3. Configure your backend API URL in `.env`:

```env
NUXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Development

Start the development server:

```bash
pnpm dev
```

The app will be available at `http://localhost:3000`

## API Types

Uses `@reviewate/api-types` package with auto-generated types from backend OpenAPI spec.

### Usage

```vue
<script setup lang="ts">
import type { paths } from '@reviewate/api-types'

const client = useApi()

const { data, error } = await client.GET('/api/repositories')
//    ^? components['schemas']['Repository'][]

const reviews = ref<paths['/api/reviews']['get']['responses']['200']['content']['application/json']>([])
</script>
```

### Local Generation

```bash
make generate-types
```

### CI Generation

Types auto-generated on backend version tags (`v1.0.0`) and committed to repo.

## Project Structure

```
frontend/
├── app/
│   ├── components/        # Vue components (auto-imported)
│   ├── composables/       # Reusable composables (auto-imported, includes useApi)
│   ├── layouts/           # Application layouts
│   ├── pages/             # Route pages (file-based routing)
│   ├── stores/            # Pinia store modules (auto-imported)
│   ├── types/             # TypeScript type definitions
│   ├── utils/             # Utility functions (auto-imported)
│   └── app.vue            # Root component
├── public/                # Static assets
├── .env                   # Environment variables (not committed)
├── .env.example           # Environment variables template
├── eslint.config.mjs      # ESLint configuration
├── nuxt.config.ts         # Nuxt configuration
├── package.json           # Dependencies and scripts
├── .prettierrc            # Prettier configuration
└── tsconfig.json          # TypeScript configuration (strict mode)
```

## Architecture

- **Framework**: Nuxt 4 (Vue 3 with auto-imports and file-based routing)
- **State Management**: Pinia (stores auto-imported from `app/stores/`)
- **API Client**: Type-safe client using @reviewate/api-types package
- **UI Components**: @nuxt/ui (Nuxt UI library)
- **TypeScript**: Strict mode enabled with comprehensive type checking
- **Code Quality**: ESLint + Prettier with Nuxt-specific rules

## Configuration Highlights

### TypeScript Strict Mode
- All strict type checking options enabled
- Additional checks for unused variables and implicit returns
- Configured in `tsconfig.json`

### ESLint & Prettier
- ESLint configured with TypeScript and Vue rules
- Prettier for consistent code formatting
- Import ordering and sorting enforced
- Stylistic rules for consistent code style

### Auto-Imports
- Components from `app/components/` are auto-imported
- Composables from `app/composables/` are auto-imported
- Stores from `app/stores/` are auto-imported
- Utils from `app/utils/` are auto-imported

## Available Scripts

- `pnpm dev` - Start development server
- `pnpm build` - Build for production
- `pnpm generate` - Generate static site
- `pnpm preview` - Preview production build
- `pnpm lint` - Lint code
- `pnpm lint:fix` - Lint and auto-fix issues
- `pnpm format` - Format code with Prettier
- `pnpm format:check` - Check code formatting
- `pnpm typecheck` - Run TypeScript type checking
