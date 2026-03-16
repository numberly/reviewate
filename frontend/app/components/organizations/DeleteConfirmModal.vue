<script setup lang="ts">
/**
 * Delete Confirm Modal Component
 *
 * Reusable confirmation modal for delete operations.
 */
defineProps<{
  open: boolean
  isLoading: boolean
  title: string
  description: string
  itemName: string
  confirmText?: string
  errorMessage?: string | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'confirm': []
  'clearError': []
}>()

function handleClose() {
  emit('update:open', false)
}

function handleConfirm() {
  emit('confirm')
}
</script>

<template>
  <UModal
    :open="open"
    @update:open="emit('update:open', $event)"
  >
    <template #header>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <div class="flex size-7 items-center justify-center rounded-full bg-error-100 dark:bg-error-900/30">
            <UIcon
              name="i-lucide-alert-triangle"
              class="size-4 text-error-600 dark:text-error-400"
            />
          </div>
          <h3 class="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
            {{ title }}
          </h3>
        </div>
        <UButton
          color="neutral"
          variant="ghost"
          size="xs"
          icon="i-lucide-x"
          @click="handleClose"
        />
      </div>
    </template>

    <template #body>
      <div class="space-y-3">
        <p class="text-sm text-neutral-600 dark:text-neutral-400">
          {{ description }}
        </p>
        <div class="rounded-lg bg-neutral-100 p-3 dark:bg-neutral-800">
          <p class="font-medium text-neutral-900 dark:text-neutral-100">
            {{ itemName }}
          </p>
        </div>
        <p class="text-sm font-medium text-error-600 dark:text-error-400">
          {{ $t('common.cannotBeUndone') }}
        </p>
        <!-- Error Alert -->
        <ErrorAlert
          :error="errorMessage ?? null"
          :auto-dismiss="false"
          @dismiss="emit('clearError')"
        />
      </div>
    </template>

    <template #footer>
      <UButton
        color="neutral"
        variant="ghost"
        size="sm"
        :disabled="isLoading"
        @click="handleClose"
      >
        {{ $t('common.cancel') }}
      </UButton>
      <UButton
        color="error"
        size="sm"
        :loading="isLoading"
        @click="handleConfirm"
      >
        {{ confirmText || $t('common.delete') }}
      </UButton>
    </template>
  </UModal>
</template>
