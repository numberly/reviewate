<script setup lang="ts">
/**
 * Error Alert Component
 *
 * Reusable animated error alert with auto-dismiss functionality.
 */
const props = withDefaults(defineProps<{
  error: string | null
  autoDismiss?: boolean
  dismissAfter?: number
}>(), {
  autoDismiss: true,
  dismissAfter: 5000,
})

const emit = defineEmits<{
  dismiss: []
}>()

let dismissTimeout: ReturnType<typeof setTimeout> | null = null

// Auto-dismiss when error changes
watch(() => props.error, (newError) => {
  if (dismissTimeout) {
    clearTimeout(dismissTimeout)
    dismissTimeout = null
  }

  if (newError && props.autoDismiss) {
    dismissTimeout = setTimeout(() => {
      emit('dismiss')
    }, props.dismissAfter)
  }
}, { immediate: true })

// Cleanup on unmount
onUnmounted(() => {
  if (dismissTimeout) {
    clearTimeout(dismissTimeout)
  }
})

function handleClose() {
  if (dismissTimeout) {
    clearTimeout(dismissTimeout)
    dismissTimeout = null
  }
  emit('dismiss')
}
</script>

<template>
  <Transition
    enter-active-class="transition-all duration-300 ease-out"
    enter-from-class="opacity-0 -translate-y-2"
    enter-to-class="opacity-100 translate-y-0"
    leave-active-class="transition-all duration-200 ease-in"
    leave-from-class="opacity-100 translate-y-0"
    leave-to-class="opacity-0 -translate-y-2"
  >
    <UAlert
      v-if="error"
      color="error"
      icon="i-lucide-alert-circle"
      :title="error"
      :close-button="{ icon: 'i-lucide-x', color: 'error', variant: 'link' }"
      @close="handleClose"
    />
  </Transition>
</template>
