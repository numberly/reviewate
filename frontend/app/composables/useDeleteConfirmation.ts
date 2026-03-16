/**
 * Composable for managing delete confirmation dialogs
 * Reusable pattern for delete operations with confirmation
 */

export interface DeleteConfirmationOptions<T> {
  /**
   * Callback to execute the delete operation
   * @returns Promise<boolean> - true if successful
   */
  onDelete: (item: T) => Promise<boolean>

  /**
   * Callback after successful deletion
   */
  onSuccess?: (item: T) => void

  /**
   * Callback to get error message when deletion fails
   * Can return a string error message or null
   */
  getError?: () => string | null
}

export function useDeleteConfirmation<T>(options: DeleteConfirmationOptions<T>) {
  const isOpen = ref(false)
  const itemToDelete = ref<T | null>(null)
  const isDeleting = ref(false)
  const error = ref<string | null>(null)
  let errorTimeout: ReturnType<typeof setTimeout> | null = null

  /**
   * Set error with auto-dismiss after 5 seconds
   */
  function setError(message: string) {
    if (errorTimeout) {
      clearTimeout(errorTimeout)
    }
    error.value = message
    errorTimeout = setTimeout(() => {
      error.value = null
    }, 5000)
  }

  /**
   * Open confirmation dialog for an item
   */
  function confirm(item: T) {
    itemToDelete.value = item
    error.value = null
    isOpen.value = true
  }

  /**
   * Close confirmation dialog
   */
  function cancel() {
    isOpen.value = false
    itemToDelete.value = null
    error.value = null
    if (errorTimeout) {
      clearTimeout(errorTimeout)
      errorTimeout = null
    }
  }

  /**
   * Execute the delete operation
   */
  async function execute() {
    if (!itemToDelete.value) return

    isDeleting.value = true
    error.value = null

    try {
      const success = await options.onDelete(itemToDelete.value)

      if (success) {
        // Call success callback if provided
        if (options.onSuccess) {
          options.onSuccess(itemToDelete.value)
        }

        // Close dialog
        cancel()
      } else {
        // Get error from callback if provided
        setError(options.getError?.() ?? 'Failed to delete. Please try again.')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete. Please try again.')
    } finally {
      isDeleting.value = false
    }
  }

  /**
   * Clear error state
   */
  function clearError() {
    error.value = null
    if (errorTimeout) {
      clearTimeout(errorTimeout)
      errorTimeout = null
    }
  }

  return {
    isOpen,
    itemToDelete,
    isDeleting: readonly(isDeleting),
    error: readonly(error),
    confirm,
    execute,
    clearError,
  }
}
