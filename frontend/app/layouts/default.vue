<script setup lang="ts">
const { t } = useI18n()

const navItems = computed(() => [
  [
    { label: t('nav.dashboard'), icon: 'i-lucide-layout-dashboard', to: '/' },
    { label: t('nav.organizations'), icon: 'i-lucide-building-2', to: '/organizations' },
  ],
  [
    { label: t('nav.settings'), icon: 'i-lucide-settings', to: '/settings' },
  ],
])

// Track active route
const route = useRoute()
const navItemsWithActive = computed(() =>
  navItems.value.map((group) =>
    group.map((item) => ({
      ...item,
      active: item.to === route.path,
    })),
  ),
)
</script>

<template>
  <UDashboardGroup
    storage="cookie"
    storage-key="dashboard-sidebar"
  >
    <!-- Sidebar -->
    <AppSidebar :items="navItemsWithActive" />

    <!-- Main Content -->
    <UDashboardPanel id="main-content">
      <template #header>
        <!-- Mobile Header - only visible on mobile -->
        <UDashboardNavbar :toggle="false">
          <template #leading>
            <UDashboardSidebarToggle
              color="neutral"
              variant="ghost"
            />
            <Logo class="size-5" />
            <span class="text-sm font-semibold text-highlighted">{{ $t('common.appName') }}</span>
          </template>
        </UDashboardNavbar>
      </template>

      <template #body>
        <!-- Page Content -->
        <div class="flex-1 flex flex-col min-h-0">
          <slot />
        </div>
      </template>
    </UDashboardPanel>
  </UDashboardGroup>
</template>
