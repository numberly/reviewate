/**
 * Test utilities for Vue component testing with Nuxt
 *
 * Provides helper functions and mocks for testing components.
 */
import { config } from '@vue/test-utils'
import { beforeAll, vi } from 'vitest'

// ============================================================================
// Mock vue-i18n useI18n for Composition API usage in components
// (the template-level $t is mocked separately via config.global.mocks below)
// ============================================================================

vi.mock('vue-i18n', async (importOriginal) => {
  const mod = await importOriginal<Record<string, unknown>>()
  return {
    ...mod,
    useI18n: () => ({
      t: (key: string) => key,
      locale: { value: 'en' },
    }),
  }
})

// ============================================================================
// Mock useApi composable to prevent network requests during tests
// ============================================================================

// Create a mock API client that returns empty responses
// Uses lowercase methods (get, post, etc.) to match @hey-api/client interface
const mockApiClient = {
  get: vi.fn().mockResolvedValue({ data: null, error: { status: 401 } }),
  post: vi.fn().mockResolvedValue({ data: null, error: null }),
  put: vi.fn().mockResolvedValue({ data: null, error: null }),
  delete: vi.fn().mockResolvedValue({ data: null, error: null }),
  patch: vi.fn().mockResolvedValue({ data: null, error: null }),
  setConfig: vi.fn(),
}

// Mock the useApi composable globally
vi.mock('~/composables/useApi', () => ({
  useApi: () => mockApiClient,
}))

// ============================================================================
// Mock useConfigStore to provide default enabled providers for tests
// ============================================================================

vi.mock('~/stores/config', () => ({
  useConfigStore: () => ({
    config: null,
    isLoading: false,
    isInitialized: true,
    isGitHubEnabled: true,
    isGitLabEnabled: true,
    isGoogleEnabled: true,
    gitLabUrl: 'https://gitlab.com',
    fetchConfig: vi.fn(),
    $reset: vi.fn(),
  }),
}))

// ============================================================================
// Suppress expected console warnings during tests
// ============================================================================

beforeAll(() => {
  // Store original console methods
  const originalWarn = console.warn
  const originalError = console.error

  console.warn = (...args: unknown[]) => {
    const message = String(args[0] ?? '')
    // Suppress Dialog accessibility warnings from Reka UI
    if (message.includes('DialogContent') || message.includes('DialogTitle')) {
      return
    }
    // Suppress Description warnings
    if (message.includes('Description') || message.includes('aria-describedby')) {
      return
    }
    originalWarn.apply(console, args)
  }

  console.error = (...args: unknown[]) => {
    originalError.apply(console, args)
  }
})

// ============================================================================
// Global Vue Test Utils Configuration
// ============================================================================

// Mock i18n $t function globally
config.global.mocks = {
  $t: (key: string) => key,
}

// Mock NuxtLink and UI components
config.global.stubs = {
  NuxtLink: {
    template: '<a :href="to"><slot /></a>',
    props: ['to'],
  },
  // Stub UTooltip to avoid TooltipProvider context requirement
  UTooltip: {
    template: '<span><slot /></span>',
    props: ['text'],
  },
  // Stub ErrorAlert to avoid proxy issues with 'error' prop name
  ErrorAlert: {
    template: '<div v-if="error" class="error-alert">{{ error }}</div>',
    props: ['error', 'autoDismiss', 'dismissAfter'],
  },
}

// Export vi and mock client for convenience
export { vi, mockApiClient }

/**
 * Create a mock organization for testing
 */
export function createMockOrganization(overrides: Partial<{
  id: string
  name: string
  external_org_id: string
  installation_id: string | null
  provider: 'github' | 'gitlab'
  created_at: string
  role: 'admin' | 'member'
}> = {}) {
  return {
    id: 'org-1',
    name: 'Test Organization',
    external_org_id: 'ext-org-123',
    installation_id: '12345',
    provider: 'github' as const,
    created_at: '2024-01-01T00:00:00Z',
    role: 'admin' as const,
    ...overrides,
  }
}

/**
 * Create a mock repository for testing
 */
export function createMockRepository(overrides: Partial<{
  id: string
  name: string
  full_name: string
  url: string
  external_id: string
  platform: string
  organization_id: string
}> = {}) {
  return {
    id: 'repo-1',
    name: 'test-repo',
    full_name: 'org/test-repo',
    url: 'https://github.com/org/test-repo',
    external_id: '123456',
    platform: 'github',
    organization_id: 'org-1',
    ...overrides,
  }
}

/**
 * Wait for a condition to be true
 */
export async function waitFor(
  condition: () => boolean,
  timeout = 1000,
  interval = 50,
): Promise<void> {
  const start = Date.now()
  while (!condition()) {
    if (Date.now() - start > timeout) {
      throw new Error('Timeout waiting for condition')
    }
    await new Promise((resolve) => setTimeout(resolve, interval))
  }
}

/**
 * Flush all pending promises
 */
export async function flushPromises(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0))
}
