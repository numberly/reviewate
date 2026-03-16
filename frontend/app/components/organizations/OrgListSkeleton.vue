<script setup lang="ts">
/**
 * Organization List Skeleton Component
 *
 * Displays a loading skeleton for the organization list.
 */
defineProps<{
  count?: number
}>()
</script>

<template>
  <CornerFrame class="flex flex-col flex-1 border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-sm overflow-hidden">
    <!-- Header -->
    <div class="px-4 py-3 border-b border-neutral-200 dark:border-neutral-700 shrink-0">
      <USkeleton class="h-5 w-28" />
    </div>

    <!-- Skeleton List -->
    <div class="divide-y divide-neutral-100 dark:divide-neutral-700 overflow-y-auto flex-1">
      <div
        v-for="i in (count ?? 4)"
        :key="i"
        class="flex items-center gap-3 px-4 py-3"
      >
        <!-- Avatar skeleton -->
        <USkeleton class="size-9 rounded-lg" />

        <!-- Content skeleton -->
        <div class="flex-1 min-w-0 space-y-2">
          <USkeleton class="h-4 w-32" />
          <USkeleton class="h-3 w-20" />
        </div>

        <!-- Arrow skeleton -->
        <USkeleton class="size-4 rounded" />
      </div>
    </div>

    <!-- Add buttons skeleton -->
    <div class="px-4 py-3 border-t border-neutral-200 dark:border-neutral-700 space-y-2 shrink-0">
      <USkeleton class="h-8 w-full rounded-md" />
      <USkeleton class="h-8 w-full rounded-md" />
    </div>
  </CornerFrame>
</template>
