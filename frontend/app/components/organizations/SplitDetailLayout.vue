<script setup lang="ts">
/**
 * Generic responsive split layout for list/detail panels.
 *
 * Desktop (md+): list at 1/3 + detail panel at 2/3 with slide transition
 * Mobile (< md): toggle between list and detail with fade transition
 */
defineProps<{
  hasSelection: boolean
}>()
</script>

<template>
  <!-- Desktop Layout (md+): Side by side -->
  <div class="hidden md:flex h-full">
    <!-- List (1/3 width when selected, full width otherwise) -->
    <div
      class="h-full overflow-hidden transition-all duration-300 ease-out"
      :class="hasSelection ? 'w-1/3 border-r border-neutral-200 dark:border-neutral-700' : 'w-full'"
    >
      <slot name="list" />
    </div>

    <!-- Detail Panel (2/3 width) -->
    <Transition
      enter-active-class="transition-all duration-300 ease-out"
      enter-from-class="opacity-0 translate-x-4"
      enter-to-class="opacity-100 translate-x-0"
      leave-active-class="transition-all duration-200 ease-in"
      leave-from-class="opacity-100 translate-x-0"
      leave-to-class="opacity-0 translate-x-4"
    >
      <div
        v-if="hasSelection"
        class="w-2/3 h-full overflow-hidden"
      >
        <slot name="detail" />
      </div>
    </Transition>
  </div>

  <!-- Mobile Layout (< md): Single panel with navigation -->
  <div class="md:hidden h-full">
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-all duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
      mode="out-in"
    >
      <!-- List -->
      <div
        v-if="!hasSelection"
        key="list"
        class="h-full"
      >
        <slot name="list" />
      </div>

      <!-- Detail (full width on mobile) -->
      <div
        v-else
        key="detail"
        class="h-full overflow-hidden"
      >
        <slot name="detail" />
      </div>
    </Transition>
  </div>
</template>
