<script setup lang="ts">
const route = useRoute()
const layoutName = computed(() => route.meta.layout as string || 'default')
</script>

<template>
  <UApp>
    <NuxtLayout :key="layoutName">
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>
