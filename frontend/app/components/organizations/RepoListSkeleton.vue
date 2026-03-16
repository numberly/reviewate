<script setup lang="ts">
/**
 * Repository List Skeleton Component
 *
 * Displays a loading skeleton for the repository list.
 */
defineProps<{
  count?: number
}>()
</script>

<template>
  <div class="h-full flex flex-col overflow-hidden">
    <!-- Header skeleton -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-neutral-200 dark:border-neutral-700 shrink-0 bg-white dark:bg-neutral-800">
      <div class="flex items-center gap-2">
        <USkeleton class="h-4 w-24" />
        <USkeleton class="h-3 w-8" />
      </div>
      <USkeleton class="h-8 w-48 rounded-md" />
    </div>

    <!-- List skeleton -->
    <div class="flex-1 overflow-y-auto divide-y divide-neutral-100 dark:divide-neutral-700">
      <div
        v-for="i in (count ?? 6)"
        :key="i"
        class="flex items-center gap-3 px-4 py-3"
      >
        <div class="flex-1 min-w-0 space-y-2">
          <div class="flex items-center gap-2">
            <USkeleton class="size-4 rounded" />
            <USkeleton class="h-4 w-36" />
          </div>
          <USkeleton class="h-3 w-16" />
        </div>
        <USkeleton class="size-4 rounded" />
      </div>
    </div>
  </div>
</template>
