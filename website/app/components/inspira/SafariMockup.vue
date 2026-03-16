<script lang="ts" setup>
interface SafariMockupProps {
  url?: string;
  width?: number;
  height?: number;
}

withDefaults(defineProps<SafariMockupProps>(), {
  url: 'reviewate.com',
  width: 1203,
  height: 753,
});
</script>

<template>
  <div class="relative rounded-xl overflow-hidden border border-neutral-200 bg-white shadow-xl">
    <!-- Browser chrome -->
    <div class="flex items-center gap-2 px-4 py-3 bg-[#f5f5f5] border-b border-neutral-200">
      <!-- Traffic lights -->
      <div class="flex items-center gap-1.5">
        <div class="size-3 rounded-full bg-[#EC6A5E]" />
        <div class="size-3 rounded-full bg-[#F4BF4F]" />
        <div class="size-3 rounded-full bg-[#61C554]" />
      </div>
      <!-- URL bar -->
      <div class="flex-1 flex justify-center">
        <div class="flex items-center gap-2 rounded-md bg-white border border-neutral-200 px-3 py-1 text-xs text-neutral-400 min-w-[260px] justify-center">
          <svg class="size-3 shrink-0" fill="none" viewBox="0 0 12 12">
            <path d="M6 1C4.343 1 3 2.343 3 4v1.5c-.552 0-1 .448-1 1v4c0 .552.448 1 1 1h6c.552 0 1-.448 1-1v-4c0-.552-.448-1-1-1V4c0-1.657-1.343-3-3-3zm0 1c1.105 0 2 .895 2 2v1.5H4V4c0-1.105.895-2 2-2z" fill="currentColor" />
          </svg>
          {{ url }}
        </div>
      </div>
      <!-- Spacer to balance traffic lights -->
      <div class="w-[52px]" />
    </div>
    <!-- Content area -->
    <div class="bg-neutral-900">
      <slot />
    </div>
  </div>
</template>
