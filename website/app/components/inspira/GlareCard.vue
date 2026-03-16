<script setup lang="ts">
import { useTimeoutFn } from '@vueuse/core';
import { ref } from 'vue';

interface GlareCardProps {
  class?: string;
}

const props = defineProps<GlareCardProps>();

const isPointerInside = ref(false);
const refElement = ref<HTMLElement | null>(null);

const state = ref({
  glare: { x: 50, y: 50 },
  background: { x: 50, y: 50 },
  rotate: { x: 0, y: 0 },
});

function handlePointerMove(event: PointerEvent) {
  const rotateFactor = 0.4;
  const rect = refElement.value?.getBoundingClientRect();
  if (rect) {
    const position = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    };
    const percentage = {
      x: (100 / rect.width) * position.x,
      y: (100 / rect.height) * position.y,
    };
    const delta = {
      x: percentage.x - 50,
      y: percentage.y - 50,
    };
    state.value.background.x = 50 + percentage.x / 4 - 12.5;
    state.value.background.y = 50 + percentage.y / 3 - 16.67;
    state.value.rotate.x = -(delta.x / 3.5) * rotateFactor;
    state.value.rotate.y = (delta.y / 2) * rotateFactor;
    state.value.glare.x = percentage.x;
    state.value.glare.y = percentage.y;
  }
}

function handlePointerEnter() {
  isPointerInside.value = true;
  useTimeoutFn(() => {
    if (isPointerInside.value && refElement.value) {
      refElement.value.style.setProperty('--duration', '0s');
    }
  }, 300);
}

function handlePointerLeave() {
  isPointerInside.value = false;
  if (refElement.value) {
    refElement.value.style.removeProperty('--duration');
    state.value.rotate = { x: 0, y: 0 };
  }
}
</script>

<template>
  <div
    ref="refElement"
    class="glare-container relative isolate [perspective:600px] transition-transform delay-[var(--delay)] duration-[var(--duration)] ease-[var(--easing)] will-change-transform"
    @pointermove="handlePointerMove"
    @pointerenter="handlePointerEnter"
    @pointerleave="handlePointerLeave"
  >
    <div
      class="grid h-full origin-center overflow-hidden rounded-2xl [transform:rotateY(var(--r-x))_rotateX(var(--r-y))] transition-transform delay-[var(--delay)] duration-[var(--duration)] ease-[var(--easing)] will-change-transform"
    >
      <!-- Content layer -->
      <div
        class="grid size-full [clip-path:inset(0_0_0_0_round_var(--radius))] [grid-area:1/1]"
      >
        <div class="size-full" :class="[props.class]">
          <slot />
        </div>
      </div>
      <!-- Glare layer -->
      <div
        class="grid size-full opacity-[var(--opacity)] mix-blend-soft-light transition-opacity delay-[var(--delay)] duration-[var(--duration)] ease-[var(--easing)] [background:radial-gradient(farthest-corner_circle_at_var(--m-x)_var(--m-y),_rgba(255,255,255,0.8)_10%,_rgba(255,255,255,0.65)_20%,_rgba(255,255,255,0)_90%)] [clip-path:inset(0_0_1px_0_round_var(--radius))] [grid-area:1/1]"
      />
    </div>
  </div>
</template>

<style scoped>
.glare-container {
  --m-x: v-bind(`${state.glare.x}%`);
  --m-y: v-bind(`${state.glare.y}%`);
  --r-x: v-bind(`${state.rotate.x}deg`);
  --r-y: v-bind(`${state.rotate.y}deg`);
  --bg-x: v-bind(`${state.background.x}%`);
  --bg-y: v-bind(`${state.background.y}%`);
  --duration: 300ms;
  --opacity: 0;
  --radius: 16px;
  --easing: ease;
  --transition: var(--duration) var(--easing);
}
.glare-container:hover {
  --opacity: 0.6;
}
</style>
