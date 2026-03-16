<script setup lang="ts">
import type { ExecutionStatusDisplay } from '~/types/pullRequest'

const props = defineProps<{
  executionDisplay: ExecutionStatusDisplay
}>()

const emit = defineEmits<{
  retry: []
}>()

const { t, te } = useI18n()

const errorMessage = computed(() => {
  const errorType = props.executionDisplay.errorType
  if (errorType && te(`errors.types.${errorType}`)) {
    return t(`errors.types.${errorType}`)
  }
  return t('errors.types.unknown')
})
</script>

<template>
  <UPopover>
    <UBadge
      color="error"
      variant="subtle"
      size="xs"
      class="inline-block w-24 text-center cursor-pointer"
    >
      {{ executionDisplay.label }}
    </UBadge>

    <template #content>
      <div class="p-3 max-w-xs space-y-2">
        <p class="text-sm text-neutral-700 dark:text-neutral-300">
          {{ errorMessage }}
        </p>
        <p
          v-if="executionDisplay.errorDetail"
          class="text-xs text-neutral-500 dark:text-neutral-400 font-mono bg-neutral-100 dark:bg-neutral-800 rounded px-2 py-1 break-words"
        >
          {{ executionDisplay.errorDetail }}
        </p>
        <UButton
          color="primary"
          variant="soft"
          size="xs"
          block
          icon="i-lucide-refresh-cw"
          @click="emit('retry')"
        >
          {{ t('common.retry') }}
        </UButton>
      </div>
    </template>
  </UPopover>
</template>
