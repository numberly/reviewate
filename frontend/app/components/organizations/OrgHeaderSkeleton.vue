<script setup lang="ts">
/**
 * Organization Header Skeleton Component
 *
 * Displays a loading skeleton for the organization header.
 */
</script>

<template>
  <div class="flex items-center justify-between px-6 py-4 border-b border-neutral-200 dark:border-neutral-700 shrink-0">
    <div class="flex items-center gap-4">
      <!-- Avatar skeleton -->
      <USkeleton class="size-12 rounded-lg" />

      <!-- Content skeleton -->
      <div class="space-y-2">
        <USkeleton class="h-6 w-40" />
        <div class="flex items-center gap-2">
          <USkeleton class="size-4 rounded" />
          <USkeleton class="h-4 w-24" />
          <USkeleton class="h-4 w-32" />
        </div>
      </div>
    </div>
  </div>
</template>
