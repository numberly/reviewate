<script setup lang="ts">
const integrations = [
  { name: 'GitHub', icon: 'lucide:github' },
  { name: 'GitLab', icon: 'simple-icons:gitlab' },
  { name: 'Docker', icon: 'simple-icons:docker' },
  { name: 'Kubernetes', icon: 'simple-icons:kubernetes' },
  { name: 'OpenAI', icon: 'simple-icons:openai' },
  { name: 'Anthropic', icon: 'simple-icons:anthropic' },
  { name: 'Google Cloud', icon: 'simple-icons:googlecloud' },
];
</script>

<template>
  <InspiraMarquee :pause-on-hover="true" class="[--duration:30s]">
    <div
      v-for="integration in integrations"
      :key="integration.name"
      class="flex items-center gap-3 rounded-xl border border-neutral-200 bg-white px-5 py-3 shadow-sm"
    >
      <UIcon :name="integration.icon" class="size-6 text-neutral-600" />
      <span class="text-sm font-medium text-neutral-700 whitespace-nowrap">{{ integration.name }}</span>
    </div>
  </InspiraMarquee>
</template>
