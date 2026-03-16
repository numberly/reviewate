<script setup lang="ts">
const configStore = useConfigStore()

// Fetch app configuration on mount (client-side only)
onMounted(() => {
  configStore.fetchConfig()
})
</script>

<template>
  <UApp>
    <NuxtRouteAnnouncer />
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>
