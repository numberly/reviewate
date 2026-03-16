<template>
  <UDashboardSidebar
    id="app-sidebar"
    resizable
    collapsible
    :min-size="12"
    :default-size="15"
    :max-size="25"
    :collapsed-size="4"
  >
    <!-- Header -->
    <template #header="{ collapsed: isCollapsed, collapse }">
      <div
        class="flex items-center w-full overflow-hidden"
        :class="isCollapsed ? 'justify-center' : 'gap-2'"
      >
        <NuxtLink
          to="/"
          class="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity"
          :class="isCollapsed ? 'justify-center' : ''"
        >
          <Logo class="size-6 shrink-0" />
          <span
            v-if="!isCollapsed"
            class="text-sm font-semibold text-neutral-900 dark:text-neutral-100 truncate whitespace-nowrap"
          >
            {{ $t('common.appName') }}
          </span>
        </NuxtLink>
        <UIcon
          v-if="!isCollapsed"
          name="i-lucide-panel-left-close"
          class="ms-auto size-4 text-neutral-400 dark:text-neutral-500 hover:text-neutral-600 dark:hover:text-neutral-300 cursor-pointer shrink-0"
          @click="collapse?.(true)"
        />
      </div>
    </template>

    <!-- Navigation (Desktop) -->
    <template #default="{ collapsed: isCollapsed, collapse }">
      <UNavigationMenu
        :items="navigationItems"
        orientation="vertical"
        :collapsed="isCollapsed"
        highlight
        :tooltip="isCollapsed"
      />

      <!-- Bottom controls: Theme, Language, Expand -->
      <div class="mt-auto flex flex-col gap-1 pt-2">
        <!-- Language switcher -->
        <UDropdownMenu
          v-if="isCollapsed"
          :items="languageMenuItems"
          :content="{ side: 'top', align: 'center' }"
        >
          <button
            type="button"
            class="cursor-pointer w-full flex justify-center p-2 rounded-lg text-neutral-500 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800 hover:text-neutral-700 dark:hover:text-neutral-200 transition-colors"
          >
            <span class="text-base">{{ currentLocaleFlag }}</span>
          </button>
        </UDropdownMenu>
        <UDropdownMenu
          v-else
          :items="languageMenuItems"
          :content="{ side: 'top', align: 'start' }"
        >
          <button
            type="button"
            class="cursor-pointer w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] font-medium text-neutral-600 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors"
          >
            <span class="text-base">{{ currentLocaleFlag }}</span>
            <span>{{ $t('settings.language') }}</span>
            <UIcon
              name="i-lucide-chevron-up"
              class="ml-auto size-4 text-neutral-400 dark:text-neutral-500"
            />
          </button>
        </UDropdownMenu>

        <!-- Theme toggle (3-way: light/dark/system) - ClientOnly because colorMode.preference differs between server/client -->
        <ClientOnly>
          <div
            v-if="isCollapsed"
            class="flex justify-center"
          >
            <button
              type="button"
              class="cursor-pointer p-2 rounded-lg w-full text-neutral-500 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800 hover:text-neutral-700 dark:hover:text-neutral-200 transition-colors"
              @click="cycleThemeCollapsed"
            >
              <UIcon
                :name="currentThemeIcon"
                class="size-[18px]"
              />
            </button>
          </div>
          <div
            v-else
            class="px-2"
          >
            <div class="relative flex w-full rounded-lg bg-neutral-100 dark:bg-neutral-800 p-0.5">
              <!-- Animated background indicator -->
              <div
                class="absolute top-0.5 bottom-0.5 rounded-md bg-white dark:bg-neutral-700 shadow-sm transition-all duration-200 ease-out"
                :style="{
                  width: `calc((100% - 4px) / 3)`,
                  left: `calc(${themeOptions.findIndex(t => t.value === themePreference)} * (100% - 4px) / 3 + 2px)`,
                }"
              />
              <button
                v-for="theme in themeOptions"
                :key="theme.value"
                type="button"
                class="cursor-pointer relative z-10 flex-1 flex justify-center p-1.5 rounded-md transition-colors duration-200"
                :class="themePreference === theme.value ? 'text-neutral-900 dark:text-neutral-100' : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200'"
                @click="setTheme(theme.value)"
              >
                <UIcon
                  :name="theme.icon"
                  class="size-4"
                />
              </button>
            </div>
          </div>
        </ClientOnly>

        <!-- Expand button - only when collapsed -->
        <button
          v-if="isCollapsed"
          type="button"
          class="cursor-pointer w-full flex justify-center p-2 rounded-lg text-neutral-500 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800 hover:text-neutral-700 dark:hover:text-neutral-200 transition-colors"
          @click="collapse?.(false)"
        >
          <UIcon
            name="i-lucide-panel-left-open"
            class="size-[18px]"
          />
        </button>
      </div>
    </template>

    <!-- Footer (Desktop) -->
    <template #footer="{ collapsed: isCollapsed }">
      <div
        class="overflow-hidden w-full"
        :class="isCollapsed ? 'flex justify-center' : ''"
      >
        <UDropdownMenu
          v-if="showUserMenu"
          :items="userMenuItems"
          :content="{ side: 'top', align: isCollapsed ? 'center' : 'start' }"
        >
          <button
            type="button"
            class="cursor-pointer w-full flex items-center gap-2.5 rounded-lg p-2 text-left hover:bg-neutral-100/50 dark:hover:bg-neutral-800/50"
            :class="isCollapsed ? 'justify-center' : ''"
          >
            <UAvatar
              :ui="{ root: 'bg-gradient-to-br from-brand-400 to-brand-600' }"
              :text="authStore.userInitials"
              size="sm"
            />
            <div
              v-if="!isCollapsed"
              class="flex items-center gap-2.5 flex-1 min-w-0"
            >
              <span class="flex-1 text-sm font-medium text-neutral-900 dark:text-neutral-100 truncate whitespace-nowrap">{{ authStore.displayName }}</span>
              <UIcon
                name="i-lucide-chevrons-up-down"
                class="size-4 text-neutral-400 dark:text-neutral-500 shrink-0"
              />
            </div>
          </button>
        </UDropdownMenu>
        <div
          v-else
          class="w-full flex items-center gap-2.5 rounded-lg p-2"
          :class="isCollapsed ? 'justify-center' : ''"
        >
          <div class="size-7 rounded-full bg-neutral-200 dark:bg-neutral-700 animate-pulse" />
          <div
            v-if="!isCollapsed"
            class="flex-1 h-4 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse"
          />
        </div>
      </div>
    </template>

    <!-- Mobile Sidebar Content (Slideover) -->
    <template #content="{ close }">
      <div class="flex flex-col h-full bg-sidebar-bg dark:bg-neutral-950">
        <!-- Mobile Header -->
        <div class="h-14 shrink-0 flex items-center gap-2 px-4 border-b border-neutral-200 dark:border-neutral-800">
          <NuxtLink
            to="/"
            class="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity"
            @click="close?.()"
          >
            <Logo class="size-6 shrink-0" />
            <span class="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
              {{ $t('common.appName') }}
            </span>
          </NuxtLink>
          <UIcon
            name="i-lucide-x"
            class="ms-auto size-5 text-neutral-400 dark:text-neutral-500 hover:text-neutral-600 dark:hover:text-neutral-300 cursor-pointer"
            @click="close?.()"
          />
        </div>

        <!-- Mobile Navigation -->
        <div class="flex-1 overflow-y-auto px-2 py-3">
          <UNavigationMenu
            :items="navigationItems"
            orientation="vertical"
            highlight
            @click="close?.()"
          />

          <!-- Mobile: Theme and Language -->
          <div class="mt-4 pt-4 border-t border-neutral-200 dark:border-neutral-800 flex flex-col gap-1">
            <!-- Theme toggle (3-way) - ClientOnly because colorMode.preference differs between server/client -->
            <ClientOnly>
              <div class="px-2.5 py-2">
                <div class="flex w-full rounded-lg bg-neutral-100 dark:bg-neutral-800 p-0.5">
                  <button
                    v-for="theme in themeOptions"
                    :key="theme.value"
                    type="button"
                    class="cursor-pointer flex-1 flex justify-center p-1.5 rounded-md transition-colors"
                    :class="themePreference === theme.value ? 'bg-white dark:bg-neutral-700 shadow-sm text-neutral-900 dark:text-neutral-100' : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200'"
                    @click="setTheme(theme.value)"
                  >
                    <UIcon
                      :name="theme.icon"
                      class="size-4"
                    />
                  </button>
                </div>
              </div>
            </ClientOnly>

            <!-- Language switcher -->
            <UDropdownMenu
              :items="languageMenuItems"
              :content="{ side: 'top', align: 'start' }"
            >
              <button
                type="button"
                class="cursor-pointer w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] font-medium text-neutral-600 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors"
              >
                <span class="text-base">{{ currentLocaleFlag }}</span>
                <span>{{ $t('settings.language') }}</span>
                <UIcon
                  name="i-lucide-chevron-up"
                  class="ml-auto size-4 text-neutral-400 dark:text-neutral-500"
                />
              </button>
            </UDropdownMenu>
          </div>
        </div>

        <!-- Mobile Footer -->
        <div class="shrink-0 border-t border-neutral-200 dark:border-neutral-800 px-2 py-2">
          <UDropdownMenu
            v-if="showUserMenu"
            :items="userMenuItems"
            :content="{ side: 'top', align: 'start' }"
          >
            <button
              type="button"
              class="cursor-pointer w-full flex items-center gap-2.5 rounded-lg p-2 text-left hover:bg-neutral-100/50 dark:hover:bg-neutral-800/50"
            >
              <UAvatar
                :ui="{ root: 'bg-gradient-to-br from-brand-400 to-brand-600' }"
                :text="authStore.userInitials"
                size="sm"
              />
              <span class="flex-1 text-sm font-medium text-neutral-900 dark:text-neutral-100 truncate">{{ authStore.displayName }}</span>
              <UIcon
                name="i-lucide-chevrons-up-down"
                class="size-4 text-neutral-400 dark:text-neutral-500 shrink-0"
              />
            </button>
          </UDropdownMenu>
          <div
            v-else
            class="w-full flex items-center gap-2.5 rounded-lg p-2"
          >
            <div class="size-7 rounded-full bg-neutral-200 dark:bg-neutral-700 animate-pulse" />
            <div class="flex-1 h-4 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
          </div>
        </div>
      </div>
    </template>
  </UDashboardSidebar>
</template>

<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

interface NavItem {
  label: string
  icon?: string
  to?: string
  badge?: string
  active?: boolean
}

interface LocaleItem {
  code: 'en' | 'fr'
  name: string
}

const props = defineProps<{
  items: NavItem[][]
}>()

const { t } = useI18n()

// Theme management
const {
  themePreference,
  currentThemeIcon,
  themeOptions,
  setTheme,
  cycleThemeCollapsed,
} = useTheme()

// i18n
const { locale, locales, setLocale } = useI18n()

// Auth store for logout
const authStore = useAuthStore()

// Ensure consistent SSR/client rendering - only show user after hydration
const isHydrated = ref(false)
onMounted(() => {
  isHydrated.value = true
})

// Show user dropdown only when hydrated AND authenticated
const showUserMenu = computed(() => isHydrated.value && authStore.isAuthenticated)

// Locale flags mapping
const localeFlags: Record<string, string> = {
  en: '🇬🇧',
  fr: '🇫🇷',
}

const currentLocaleFlag = computed(() => localeFlags[locale.value] || '🌐')

const availableLocales = computed<LocaleItem[]>(() =>
  locales.value
    .filter((l): l is { code: 'en' | 'fr', name: string } =>
      typeof l === 'object' && 'code' in l && 'name' in l,
    )
    .map((l) => ({ code: l.code, name: l.name })),
)

// Transform nav items to NavigationMenu format
const navigationItems = computed<NavigationMenuItem[][]>(() =>
  props.items.map((group) =>
    group.map((item) => ({
      label: item.label,
      icon: item.icon,
      to: item.to,
      badge: item.badge,
      active: item.active,
    })),
  ),
)

// Tour
const { replayTour } = useTour()

// User menu items for dropdown (simplified - dark mode and language moved to sidebar)
const userMenuItems = computed(() => [
  [
    {
      type: 'label' as const,
      label: authStore.user?.display_username || authStore.user?.email || '',
    },
  ],
  [
    {
      label: t('settings.title'),
      icon: 'i-lucide-settings',
      to: '/settings',
    },
    {
      label: t('tour.replay'),
      icon: 'i-lucide-compass',
      onSelect: () => replayTour(),
    },
  ],
  [
    {
      label: t('settings.signOut'),
      icon: 'i-lucide-log-out',
      color: 'error' as const,
      onSelect: () => authStore.logout(),
    },
  ],
])

// Language menu items for dropdown with flags
const languageMenuItems = computed(() => [
  availableLocales.value.map((loc) => ({
    label: `${localeFlags[loc.code] || '🌐'}  ${loc.name}`,
    icon: locale.value === loc.code ? 'i-lucide-check' : undefined,
    onSelect: () => setLocale(loc.code),
  })),
])
</script>
