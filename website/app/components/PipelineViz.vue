<script setup lang="ts">
const stages = ['Analyze (×2)', 'Fact-Check', 'Style']
</script>

<template>
  <div class="flex flex-col sm:flex-row items-center justify-center gap-3">
    <template v-for="(stage, i) in stages" :key="stage">
      <div class="px-5 py-3 rounded-xl bg-white border border-neutral-200 text-sm font-semibold text-neutral-700 shadow-sm whitespace-nowrap">
        {{ stage }}
      </div>
      <UIcon
        v-if="i < stages.length - 1"
        name="lucide:chevron-right"
        class="size-4 text-neutral-300 hidden sm:block"
      />
      <UIcon
        v-if="i < stages.length - 1"
        name="lucide:chevron-down"
        class="size-4 text-neutral-300 sm:hidden"
      />
    </template>
  </div>
</template>
