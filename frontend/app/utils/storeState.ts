/**
 * Store State Helper
 *
 * Provides common loading/error state management for Pinia stores.
 * Reduces boilerplate by centralizing the loading/error pattern.
 */

export interface StoreState {
  isLoading: Ref<boolean>
  error: Ref<string | null>
  clearError: () => void
}

export interface StoreStateWithAction extends StoreState {
  /**
   * Wrap an async function with loading/error handling
   *
   * @param fn - The async function to execute
   * @param errorMessage - Default error message if an error occurs
   * @returns The result of the async function, or null if an error occurred
   *
   * @example
   * ```ts
   * const result = await withLoading(
   *   async () => {
   *     const { data, error } = await apiCall()
   *     if (error) throw new Error('API error')
   *     return data
   *   },
   *   'Failed to load data'
   * )
   * ```
   */
  withLoading: <T>(fn: () => Promise<T>, errorMessage?: string) => Promise<T | null>
}

/**
 * Create loading/error state management for a store
 *
 * @example Basic usage in a Pinia store
 * ```ts
 * export const useMyStore = defineStore('my', () => {
 *   const { isLoading, error, clearError, withLoading } = useStoreState()
 *
 *   async function fetchData() {
 *     return await withLoading(async () => {
 *       const { data, error } = await api.getData()
 *       if (error) throw new Error('API error')
 *       myData.value = data
 *       return true
 *     }, 'Failed to fetch data')
 *   }
 *
 *   return { isLoading, error, clearError, fetchData }
 * })
 * ```
 */
export function useStoreState(): StoreStateWithAction {
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  function clearError(): void {
    error.value = null
  }

  async function withLoading<T>(
    fn: () => Promise<T>,
    errorMessage: string = 'An error occurred',
  ): Promise<T | null> {
    isLoading.value = true
    error.value = null

    try {
      return await fn()
    } catch (e) {
      console.error('[Store] Error:', e)
      error.value = e instanceof Error ? e.message : errorMessage
      return null
    } finally {
      isLoading.value = false
    }
  }

  return {
    isLoading,
    error,
    clearError,
    withLoading,
  }
}

/**
 * Create multiple loading states for stores that have separate loading indicators
 * (e.g., isLoading for fetching vs isDeleting for deletion)
 *
 * @example
 * ```ts
 * const { isLoading, error, withLoading } = useStoreState()
 * const { isLoading: isDeleting, withLoading: withDeleting } = useStoreState()
 * ```
 */

/**
 * Type helper to pick only the state refs from store state
 * Useful for exposing state in store's return without actions
 */
export type StoreStateRefs = Pick<StoreState, 'isLoading' | 'error'>

/**
 * Get initial state values for $reset implementations
 */
export function getInitialStoreState() {
  return {
    isLoading: false,
    error: null as string | null,
  }
}
