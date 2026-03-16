<script setup lang="ts">
/**
 * Organization Settings Skeleton Component
 *
 * Displays a loading skeleton for the organization settings panel.
 * Mimics the OrgGeneralTab layout.
 */
</script>

<template>
  <div class="flex flex-col h-full overflow-hidden">
    <!-- Header Skeleton -->
    <OrgHeaderSkeleton />

    <!-- Tabs Skeleton -->
    <div class="border-b border-neutral-200 dark:border-neutral-700 px-6 shrink-0">
      <nav class="flex gap-6">
        <div
          v-for="i in 2"
          :key="i"
          class="py-3"
        >
          <div class="flex items-center gap-2">
            <USkeleton class="size-4 rounded" />
            <USkeleton class="h-4 w-20" />
          </div>
        </div>
      </nav>
    </div>

    <!-- Content Skeleton -->
    <div class="p-6 overflow-y-auto flex-1">
      <div class="space-y-6">
        <!-- Section 1 -->
        <div class="space-y-4">
          <div class="flex items-center gap-2">
            <USkeleton class="size-4 rounded" />
            <USkeleton class="h-4 w-32" />
          </div>
          <div class="rounded-lg border border-neutral-200 dark:border-neutral-700 p-4 space-y-4">
            <div class="space-y-2">
              <USkeleton class="h-4 w-24" />
              <USkeleton class="h-10 w-full rounded-md" />
            </div>
            <div class="space-y-2">
              <USkeleton class="h-4 w-20" />
              <USkeleton class="h-10 w-full rounded-md" />
            </div>
          </div>
        </div>

        <!-- Section 2 -->
        <div class="space-y-4">
          <div class="flex items-center gap-2">
            <USkeleton class="size-4 rounded" />
            <USkeleton class="h-4 w-28" />
          </div>
          <div class="rounded-lg border border-neutral-200 dark:border-neutral-700 p-4 space-y-4">
            <div class="flex items-center justify-between">
              <div class="space-y-1">
                <USkeleton class="h-4 w-32" />
                <USkeleton class="h-3 w-48" />
              </div>
              <USkeleton class="h-5 w-9 rounded-full" />
            </div>
            <USkeleton class="h-px w-full" />
            <div class="flex items-center justify-between">
              <div class="space-y-1">
                <USkeleton class="h-4 w-36" />
                <USkeleton class="h-3 w-44" />
              </div>
              <USkeleton class="h-5 w-9 rounded-full" />
            </div>
          </div>
        </div>

        <!-- Section 3 -->
        <div class="space-y-4">
          <div class="flex items-center gap-2">
            <USkeleton class="size-4 rounded" />
            <USkeleton class="h-4 w-24" />
          </div>
          <div class="rounded-lg border border-neutral-200 dark:border-neutral-700 p-4 space-y-4">
            <div class="flex items-center justify-between">
              <div class="space-y-1">
                <USkeleton class="h-4 w-28" />
                <USkeleton class="h-3 w-40" />
              </div>
              <USkeleton class="h-5 w-9 rounded-full" />
            </div>
            <USkeleton class="h-px w-full" />
            <div class="flex items-center justify-between">
              <div class="space-y-1">
                <USkeleton class="h-4 w-32" />
                <USkeleton class="h-3 w-36" />
              </div>
              <USkeleton class="h-5 w-9 rounded-full" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
