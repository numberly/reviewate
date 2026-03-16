<script setup lang="ts">
import { onMounted, ref } from "vue";

const containerRef = ref<HTMLElement>();
const centerRef = ref<HTMLElement>();
const leftRefs = ref<HTMLElement[]>([]);
const rightRefs = ref<HTMLElement[]>([]);
const ready = ref(false);

const leftIcons = [
  { label: 'GitHub', icon: 'lucide:github' },
  { label: 'GitLab', icon: 'simple-icons:gitlab' },
  { label: 'Docker', icon: 'simple-icons:docker' },
];

const rightIcons = [
  { label: 'OpenAI', icon: 'simple-icons:openai' },
  { label: 'Anthropic', icon: 'simple-icons:anthropic' },
  { label: 'Google Cloud', icon: 'simple-icons:googlecloud' },
];

function setLeftRef(el: any, i: number) {
  if (el) leftRefs.value[i] = el as HTMLElement;
}

function setRightRef(el: any, i: number) {
  if (el) rightRefs.value[i] = el as HTMLElement;
}

onMounted(() => {
  setTimeout(() => { ready.value = true; }, 100);
});

// Curvature: top icons arc up, middle straight, bottom icons arc down
const leftCurvatures = [75, 0, -75];
const rightCurvatures = [75, 0, -75];
</script>

<template>
  <div ref="containerRef" class="relative flex items-center justify-center gap-12 sm:gap-24 py-8">
    <!-- Left column -->
    <div class="flex flex-col items-center gap-8 sm:gap-10">
      <div
        v-for="(item, i) in leftIcons"
        :key="item.label"
        :ref="(el) => setLeftRef(el, i)"
        class="z-10 flex size-12 sm:size-14 items-center justify-center rounded-xl border-2 border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 shadow-sm"
      >
        <UIcon :name="item.icon" class="size-6 sm:size-7 text-neutral-700 dark:text-neutral-300" />
      </div>
    </div>

    <!-- Center: Reviewate logo -->
    <div
      ref="centerRef"
      class="z-10 flex size-16 sm:size-20 items-center justify-center rounded-2xl border-2 border-brand-200 dark:border-brand-700 bg-white dark:bg-neutral-900 shadow-lg"
    >
      <img src="/logo.svg" alt="Reviewate" class="size-10 sm:size-12" />
    </div>

    <!-- Right column -->
    <div class="flex flex-col items-center gap-8 sm:gap-10">
      <div
        v-for="(item, i) in rightIcons"
        :key="item.label"
        :ref="(el) => setRightRef(el, i)"
        class="z-10 flex size-12 sm:size-14 items-center justify-center rounded-xl border-2 border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 shadow-sm"
      >
        <UIcon :name="item.icon" class="size-6 sm:size-7 text-neutral-700 dark:text-neutral-300" />
      </div>
    </div>

    <!-- Animated beams -->
    <template v-if="ready && containerRef && centerRef">
      <!-- Left to center beams -->
      <InspiraAnimatedBeam
        v-for="(item, i) in leftIcons"
        :key="`left-${i}`"
        :container-ref="containerRef"
        :from-ref="leftRefs[i]"
        :to-ref="centerRef"
        :curvature="leftCurvatures[i]"
        :duration="4 + i * 0.8"
        path-color="rgb(210, 227, 228)"
        :path-opacity="0.4"
        gradient-start-color="#06483C"
        gradient-stop-color="#428A80"
      />
      <!-- Right to center beams (reverse) -->
      <InspiraAnimatedBeam
        v-for="(item, i) in rightIcons"
        :key="`right-${i}`"
        :container-ref="containerRef"
        :from-ref="rightRefs[i]"
        :to-ref="centerRef"
        :curvature="rightCurvatures[i]"
        :duration="4 + i * 0.8"
        :reverse="true"
        path-color="rgb(210, 227, 228)"
        :path-opacity="0.4"
        gradient-start-color="#06483C"
        gradient-stop-color="#428A80"
      />
    </template>
  </div>
</template>
