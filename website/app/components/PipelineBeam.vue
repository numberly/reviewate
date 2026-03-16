<script setup lang="ts">
import { onMounted, ref } from "vue";

const stages = [
  { label: 'Issue Explorer', icon: 'lucide:file-search' },
  { label: 'Analyze (×2)', icon: 'lucide:search' },
  { label: 'Synthesizer', icon: 'lucide:merge' },
  { label: 'Deduplicate', icon: 'lucide:copy-minus' },
  { label: 'Fact-Check', icon: 'lucide:shield-check' },
  { label: 'Style', icon: 'lucide:paintbrush' },
];

const containerRef = ref<HTMLElement>();
const nodeRefs = ref<HTMLElement[]>([]);
const isDesktop = ref(true);
const ready = ref(false);

function setNodeRef(el: any, i: number) {
  if (el) nodeRefs.value[i] = el as HTMLElement;
}

onMounted(() => {
  const mq = window.matchMedia('(min-width: 768px)');
  isDesktop.value = mq.matches;
  mq.addEventListener('change', (e) => {
    isDesktop.value = e.matches;
  });
  // Small delay to ensure refs are positioned
  setTimeout(() => { ready.value = true; }, 100);
});
</script>

<template>
  <div ref="containerRef" class="relative">
    <!-- Desktop: horizontal with beams -->
    <div class="flex flex-col md:flex-row items-center justify-center gap-6 md:gap-4 lg:gap-6">
      <template v-for="(stage, i) in stages" :key="stage.label">
        <div
          :ref="(el) => setNodeRef(el, i)"
          class="flex flex-col items-center gap-2 z-10"
        >
          <div class="size-12 lg:size-14 rounded-full bg-white dark:bg-neutral-900 border-2 border-brand-200 dark:border-brand-700 flex items-center justify-center shadow-sm hover:shadow-md hover:border-brand-400 transition-all">
            <UIcon :name="stage.icon" class="size-5 lg:size-6 text-brand-500 dark:text-brand-400" />
          </div>
          <span class="text-xs lg:text-sm font-semibold text-neutral-700 dark:text-neutral-300 text-center whitespace-nowrap">{{ stage.label }}</span>
        </div>
        <!-- Mobile fallback: chevrons -->
        <UIcon
          v-if="i < stages.length - 1 && !isDesktop"
          name="lucide:chevron-down"
          class="size-4 text-neutral-300 md:hidden"
        />
      </template>
    </div>

    <!-- Animated beams (desktop only) -->
    <template v-if="isDesktop && ready && containerRef">
      <InspiraAnimatedBeam
        v-for="i in (stages.length - 1)"
        :key="`beam-${i}`"
        :container-ref="containerRef"
        :from-ref="nodeRefs[i - 1]"
        :to-ref="nodeRefs[i]"
        :curvature="0"
        :duration="4 + i * 0.5"
        path-color="rgb(210, 227, 228)"
        :path-opacity="0.4"
        gradient-start-color="#06483C"
        gradient-stop-color="#428A80"
      />
    </template>
  </div>
</template>
