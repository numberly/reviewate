<script setup lang="ts">
/**
 * Setting Section Component
 *
 * Groups related settings with a header and optional card container.
 * Used in organization and repository settings pages.
 */

defineProps<{
  /** Section title */
  title: string
  /** Icon name (Lucide icon) */
  icon: string
  /** Whether this is a danger zone section (red styling) */
  danger?: boolean
}>()
</script>

<template>
  <div class="space-y-4">
    <!-- Section Header -->
    <h3
      class="text-sm font-semibold flex items-center gap-2"
      :class="danger
        ? 'text-error-600 dark:text-error-400'
        : 'text-neutral-900 dark:text-neutral-100'"
    >
      <UIcon
        :name="icon"
        class="size-4"
      />
      {{ title }}
    </h3>

    <!-- Section Content -->
    <UCard :class="danger ? 'border-error-200 dark:border-error-800' : ''">
      <div class="space-y-4">
        <slot />
      </div>
    </UCard>
  </div>
</template>
