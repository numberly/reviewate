<script setup lang="ts">
const canonicalUrl = useRequestURL().href

useSeoMeta({
  title: 'Pricing - Reviewate',
  description: 'Reviewate is free and open source. Self-host for free or use our cloud platform.',
  ogTitle: 'Pricing - Reviewate',
  ogDescription: 'Reviewate is free and open source. Self-host for free or use our cloud platform.',
  ogImage: 'https://reviewate.com/og-image.png',
  ogUrl: canonicalUrl,
  twitterCard: 'summary_large_image',
  twitterTitle: 'Pricing - Reviewate',
  twitterDescription: 'Reviewate is free and open source. Self-host for free or use our cloud platform.',
  twitterImage: 'https://reviewate.com/og-image.png',
})

useHead({
  link: [{ rel: 'canonical', href: canonicalUrl }],
  script: [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'SoftwareApplication',
        'name': 'Reviewate',
        'applicationCategory': 'DeveloperApplication',
        'operatingSystem': 'Linux, Docker, Kubernetes',
        'description': 'AI-powered code review agent with multi-agent pipeline and fact-checking. Open source.',
        'url': 'https://reviewate.com',
        'offers': {
          '@type': 'Offer',
          'price': '0',
          'priceCurrency': 'USD',
        },
      }),
    },
  ],
})

const selfHostedFeatures = [
  'Unlimited repositories',
  'Unlimited reviews',
  'Full multi-agent pipeline',
  'GitHub & GitLab support',
  'Bring your own LLM',
  'Docker & Kubernetes',
  'AGPL v3 licensed',
]

const cloudFeatures = [
  'Everything in Self-Hosted',
  'Managed infrastructure',
  'No LLM API keys needed',
  'Team dashboard',
]
</script>

<template>
  <div>
    <UPageHero
      title="Simple, transparent pricing"
      description="Open source and free to self-host. A managed cloud version is coming soon."
      :ui="{ container: 'py-16 sm:py-24 lg:py-28' }"
    />

    <UPageSection>
      <div class="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
        <!-- Self-Hosted -->
        <div class="rounded-2xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-8 flex flex-col">
          <h3 class="text-xl font-bold text-neutral-900 dark:text-neutral-100">Self-Hosted</h3>
          <p class="text-sm text-neutral-500 dark:text-neutral-400 mt-1">Run on your own infrastructure. Full control.</p>
          <div class="mt-6">
            <span class="text-4xl font-bold text-neutral-900 dark:text-neutral-100">Free</span>
            <span class="text-sm text-neutral-400 ml-2">Forever</span>
          </div>
          <ul class="mt-8 space-y-3 flex-1">
            <li
              v-for="feature in selfHostedFeatures"
              :key="feature"
              class="flex items-center gap-3 text-sm text-neutral-600 dark:text-neutral-300"
            >
              <UIcon name="lucide:check" class="size-4 text-brand-500 dark:text-brand-400 shrink-0" />
              {{ feature }}
            </li>
          </ul>
          <UButton
            to="https://github.com/numberly/reviewate"
            target="_blank"
            color="neutral"
            variant="outline"
            icon="lucide:github"
            label="View on GitHub"
            block
            size="lg"
            class="mt-8"
          />
        </div>

        <!-- Cloud (highlighted with BorderBeam) -->
        <div class="relative rounded-2xl border border-brand-200 dark:border-brand-700 bg-neutral-50 dark:bg-neutral-800 p-8 flex flex-col">
          <InspiraBorderBeam
            color-from="#06483C"
            color-to="#428A80"
            :size="200"
            :duration="12"
            :border-width="2"
          />
          <div class="flex items-center gap-3">
            <h3 class="text-xl font-bold text-neutral-900 dark:text-neutral-100">Cloud</h3>
            <UBadge color="primary" variant="subtle" size="sm">Soon</UBadge>
          </div>
          <p class="text-sm text-neutral-500 dark:text-neutral-400 mt-1">Managed platform. No setup required.</p>
          <div class="mt-6">
            <span class="text-4xl font-bold text-neutral-900 dark:text-neutral-100">Coming Soon</span>
          </div>
          <ul class="mt-8 space-y-3 flex-1">
            <li
              v-for="feature in cloudFeatures"
              :key="feature"
              class="flex items-center gap-3 text-sm text-neutral-600 dark:text-neutral-300"
            >
              <UIcon name="lucide:check" class="size-4 text-brand-500 dark:text-brand-400 shrink-0" />
              {{ feature }}
            </li>
          </ul>
          <UButton
            color="neutral"
            label="Coming Soon"
            block
            size="lg"
            class="mt-8"
            disabled
          />
        </div>
      </div>
    </UPageSection>

    <UPageCTA
      title="Questions about pricing?"
      description="Reviewate is open source and always will be. Self-host it today or wait for our managed cloud — coming soon."
      :links="[
        { label: 'View on GitHub', to: 'https://github.com/numberly/reviewate', target: '_blank', color: 'neutral', size: 'xl', icon: 'lucide:github' },
      ]"
    />
  </div>
</template>
