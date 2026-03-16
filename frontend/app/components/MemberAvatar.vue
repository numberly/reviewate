<script setup lang="ts">
/**
 * Member Avatar Component
 *
 * Displays a member's avatar with fallback to first letter of username.
 * Handles image load errors gracefully (e.g., CORS issues with self-hosted GitLab).
 */
const props = defineProps<{
  src?: string | null
  username?: string | null
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
}>()

const hasError = ref(false)

// Reset error state when src changes
watch(() => props.src, () => {
  hasError.value = false
})

const sizeClasses = computed(() => {
  switch (props.size) {
    case 'xs': return 'size-6 text-xs'
    case 'sm': return 'size-8 text-xs'
    case 'md': return 'size-10 text-sm'
    case 'lg': return 'size-12 text-base'
    case 'xl': return 'size-14 text-lg'
    default: return 'size-8 text-xs'
  }
})

const initial = computed(() => {
  return (props.username ?? '?').charAt(0).toUpperCase()
})

const showImage = computed(() => {
  return props.src && !hasError.value
})

function handleError() {
  hasError.value = true
}
</script>

<template>
  <div
    class="rounded-full overflow-hidden flex items-center justify-center bg-neutral-200 dark:bg-neutral-700"
    :class="sizeClasses"
  >
    <img
      v-if="showImage"
      :src="src!"
      :alt="username || 'Member'"
      class="size-full object-cover"
      referrerpolicy="no-referrer"
      @error="handleError"
    />
    <span
      v-else
      class="font-medium text-neutral-600 dark:text-neutral-300"
    >
      {{ initial }}
    </span>
  </div>
</template>
