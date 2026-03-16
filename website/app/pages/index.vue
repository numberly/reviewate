<script setup lang="ts">
const canonicalUrl = useRequestURL().href

useSeoMeta({
  title: 'Reviewate - AI Code Reviews That Catch Real Bugs',
  description: 'Reviewate runs multiple AI agents on every PR. Every finding is verified against your codebase. No hallucinations. Open source.',
  ogTitle: 'Reviewate - AI Code Reviews That Catch Real Bugs',
  ogDescription: 'Reviewate runs multiple AI agents on every PR. Every finding is verified against your codebase.',
  ogImage: 'https://reviewate.com/og-image.png',
  ogUrl: canonicalUrl,
  twitterCard: 'summary_large_image',
  twitterTitle: 'Reviewate - AI Code Reviews That Catch Real Bugs',
  twitterDescription: 'Reviewate runs multiple AI agents on every PR. Every finding is verified against your codebase.',
  twitterImage: 'https://reviewate.com/og-image.png',
})

useHead({
  link: [{ rel: 'canonical', href: canonicalUrl }],
  script: [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@graph': [
          {
            '@type': 'WebSite',
            'name': 'Reviewate',
            'url': 'https://reviewate.com',
          },
          {
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
          },
        ],
      }),
    },
  ],
})

const differentiators = [
  {
    icon: 'lucide:search',
    title: 'Finds real bugs',
    description: 'Not linting. Catches null refs, race conditions, security flaws. Every finding is fact-checked against your codebase.',
  },
  {
    icon: 'lucide:server',
    title: 'Open source, self-hosted',
    description: 'AGPL v3. Run on your infrastructure. Your code never leaves your network.',
  },
  {
    icon: 'lucide:blocks',
    title: 'Any LLM, any platform',
    description: 'OpenAI, Anthropic, Google, or any compatible provider. GitHub & GitLab. Docker or Kubernetes.',
  },
]

const testimonials = [
  {
    quote: 'The fact-checker is a game changer. We went from mass-ignoring AI reviews to actually reading them.',
    author: 'Staff Engineer',
    role: 'Numberly',
    company: 'Numberly',
  },
  {
    quote: 'We self-host it behind our VPN. No code leaves our network. That was the dealbreaker for us.',
    author: 'Platform Lead',
    role: 'Numberly',
    company: 'Numberly',
  },
  {
    quote: 'It caught a race condition in our payment flow that three human reviewers missed. Paid for itself day one.',
    author: 'Senior Backend Engineer',
    role: 'Numberly',
    company: 'Numberly',
  },
  {
    quote: 'Low noise, real findings. We plugged it into GitLab CI and forgot about it — in the best way.',
    author: 'Engineering Manager',
    role: 'Numberly',
    company: 'Numberly',
  },
]
</script>

<template>
  <div>
    <!-- 1. Hero + Product Demo -->
    <div class="relative overflow-hidden">
      <!-- Flickering grid background -->
      <div class="absolute inset-0">
        <InspiraFlickeringGrid
          :square-size="4"
          :grid-gap="6"
          :flicker-chance="0.3"
          color="rgb(6, 72, 60)"
          :max-opacity="0.15"
          class="absolute inset-0 size-full"
        />
        <div class="absolute inset-0 bg-gradient-to-b from-white/60 via-transparent to-white dark:from-neutral-950/60 dark:to-neutral-950" />
      </div>

      <!-- Hero content -->
      <div class="relative mx-auto max-w-7xl px-4 sm:px-6 pt-16 sm:pt-24 lg:pt-32 pb-12 sm:pb-16">
        <div class="flex flex-col items-center text-center gap-6 sm:gap-8">
          <h1>
            <InspiraTextGenerateEffect
              words="AI code reviews that catch real bugs."
              :duration="0.6"
              class="text-4xl sm:text-5xl lg:text-6xl text-pretty tracking-tight font-bold text-neutral-900 dark:text-neutral-100 max-w-4xl"
            />
          </h1>

          <p class="max-w-2xl text-lg sm:text-xl text-neutral-500 dark:text-neutral-400 text-pretty leading-relaxed">
            Reviewate runs multiple AI agents on every PR. Every finding is verified against your actual codebase. No hallucinations.
          </p>

          <div class="flex flex-wrap items-center justify-center gap-4 pt-2">
            <UTooltip text="Coming soon" :delay-duration="0">
              <InspiraShimmerButton class="text-base font-semibold opacity-50 cursor-not-allowed" disabled>
                Get Started
                <UIcon name="lucide:arrow-right" class="size-4 ml-2" />
              </InspiraShimmerButton>
            </UTooltip>
            <UButton
              to="https://github.com/numberly/reviewate"
              target="_blank"
              color="neutral"
              variant="outline"
              size="xl"
              icon="lucide:github"
              label="View on GitHub"
            />
          </div>
        </div>
      </div>

      <!-- Product Demo -->
      <div class="relative mx-auto max-w-4xl px-4 sm:px-6 pb-16 sm:pb-24">
        <div class="relative max-w-2xl mx-auto rounded-2xl overflow-hidden">
          <ReviewDemo />
          <InspiraBorderBeam
            color-from="#06483C"
            color-to="#428A80"
            :size="250"
            :duration="12"
            :border-width="2"
          />
        </div>
      </div>
    </div>

    <!-- 3. Proof (Stats Bar) -->
    <div class="border-y border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-950">
      <div class="mx-auto max-w-5xl px-4 sm:px-6 py-12 sm:py-16">
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-8 sm:gap-12 text-center">
          <div>
            <div class="text-4xl sm:text-5xl font-bold tracking-tight">
              <InspiraNumberTicker :value="65.7" :duration="1000" />
              <span class="text-brand-500 dark:text-brand-400">%</span>
            </div>
            <div class="mt-2 text-sm font-medium text-neutral-500">Recall (number of bug caught)</div>
          </div>
          <div>
            <div class="text-4xl sm:text-5xl font-bold tracking-tight">
              <InspiraNumberTicker :value="57.3" :duration="1000" :delay="200" />
              <span class="text-brand-500 dark:text-brand-400">%</span>
            </div>
            <div class="mt-2 text-sm font-medium text-neutral-500">Precision</div>
          </div>
          <div>
            <div class="text-4xl sm:text-5xl font-bold text-brand-500 dark:text-brand-400 tracking-tight">&lt;3 min</div>
            <div class="mt-2 text-sm font-medium text-neutral-500">per review, any PR size</div>
          </div>
        </div>
        <p class="mt-8 text-center text-xs text-neutral-400">
          Benchmarked with Gemini 3 Flash on 50 real PRs across
          <a href="https://github.com/adamsaimi/sentry-20260213-0023" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2 hover:text-neutral-600 dark:hover:text-neutral-300 transition-colors">Sentry</a>,
          <a href="https://github.com/adamsaimi/grafana-20260213-0023" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2 hover:text-neutral-600 dark:hover:text-neutral-300 transition-colors">Grafana</a>,
          <a href="https://github.com/adamsaimi/keycloak-20260213-0023" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2 hover:text-neutral-600 dark:hover:text-neutral-300 transition-colors">Keycloak</a>,
          <a href="https://github.com/adamsaimi/cal_dot_com-20260213-0023" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2 hover:text-neutral-600 dark:hover:text-neutral-300 transition-colors">Cal.com</a>
          &
          <a href="https://github.com/adamsaimi/discourse-20260213-0023" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2 hover:text-neutral-600 dark:hover:text-neutral-300 transition-colors">Discourse</a>.
        </p>
        <p class="mt-8 text-center text-xs text-neutral-400">
          Based on the Augment Code benchmark. Full results and methodology available at:
          <a
            href="https://www.augmentcode.com/blog/we-benchmarked-7-ai-code-review-tools-on-real-world-prs-here-are-the-results"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-0.5 underline underline-offset-2 hover:text-neutral-600 dark:hover:text-neutral-300 transition-colors"
          >
            Source
            <UIcon name="lucide:external-link" class="size-3" />
          </a>
        </p>
      </div>
    </div>

    <!-- 4. Three Differentiators -->
    <div class="mx-auto max-w-7xl px-4 sm:px-6 py-20 sm:py-28">
      <h2 class="sr-only">Why Reviewate</h2>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <InspiraGlareCard
          v-for="diff in differentiators"
          :key="diff.title"
          class="bg-neutral-900"
        >
          <div class="flex flex-col justify-center h-full p-8 text-white">
            <UIcon :name="diff.icon" class="size-8 text-brand-300 mb-4" />
            <h3 class="text-lg font-bold mb-2">{{ diff.title }}</h3>
            <p class="text-sm text-neutral-400 leading-relaxed">{{ diff.description }}</p>
          </div>
        </InspiraGlareCard>
      </div>
    </div>

    <!-- 5. Testimonials -->
    <div class="mx-auto max-w-7xl px-4 sm:px-6 py-20 sm:py-28">
      <ClientOnly>
        <InspiraDesignTestimonials :testimonials="testimonials" />
      </ClientOnly>
    </div>

    <!-- 6. Pipeline -->
    <div class="bg-neutral-50 dark:bg-neutral-900">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 py-20 sm:py-28">
        <div class="text-center mb-12">
          <h2 class="text-3xl sm:text-4xl font-bold tracking-tight text-neutral-900 dark:text-neutral-100">
            Six stages. Every finding verified.
          </h2>
        </div>

        <PipelineBeam />
      </div>
    </div>

    <!-- 7. Integrations -->
    <div class="mx-auto max-w-7xl px-4 sm:px-6 py-20 sm:py-28">
      <div class="text-center mb-8">
        <h2 class="text-3xl sm:text-4xl font-bold tracking-tight text-neutral-900 dark:text-neutral-100">
          Works with your stack
        </h2>
      </div>
      <ClientOnly>
        <IntegrationBeam />
      </ClientOnly>
    </div>

    <!-- 8. Deploy + CTA -->
    <div class="mx-auto max-w-7xl px-4 sm:px-6 pb-20 sm:pb-28">
      <div class="grid md:grid-cols-2 gap-6">
        <!-- Deploy card -->
        <div class="rounded-xl bg-neutral-900 p-6 flex flex-col">
          <div class="flex items-center gap-2 mb-4">
            <UIcon name="lucide:terminal" class="size-5 text-brand-300" />
            <span class="text-sm font-semibold text-neutral-300">Quick Start</span>
          </div>
          <div class="font-mono text-sm text-neutral-300 flex-1">
            <div class="text-neutral-500"># Deploy with Docker Compose</div>
            <div class="mt-1">
              <span class="text-brand-300">$</span> git clone https://github.com/numberly/reviewate
            </div>
            <div class="mt-1">
              <span class="text-brand-300">$</span> cp .env.example .env
            </div>
            <div class="mt-1">
              <span class="text-brand-300">$</span> docker compose --profile all up -d
            </div>
          </div>
        </div>
        <!-- Config card -->
        <div class="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-6 flex flex-col">
          <div class="flex items-center gap-2 mb-4">
            <UIcon name="lucide:settings" class="size-5 text-brand-500 dark:text-brand-400" />
            <span class="text-sm font-semibold text-neutral-700 dark:text-neutral-300">Configuration</span>
          </div>
          <ul class="space-y-3 flex-1">
            <li class="flex items-start gap-3 text-sm text-neutral-600 dark:text-neutral-300">
              <UIcon name="lucide:check" class="size-4 text-brand-500 dark:text-brand-400 mt-0.5 shrink-0" />
              <span>Choose your LLM — OpenAI, Anthropic, Google, or any OpenAI-compatible API</span>
            </li>
            <li class="flex items-start gap-3 text-sm text-neutral-600 dark:text-neutral-300">
              <UIcon name="lucide:check" class="size-4 text-brand-500 dark:text-brand-400 mt-0.5 shrink-0" />
              <span>Custom review rules per repository</span>
            </li>
            <li class="flex items-start gap-3 text-sm text-neutral-600 dark:text-neutral-300">
              <UIcon name="lucide:check" class="size-4 text-brand-500 dark:text-brand-400 mt-0.5 shrink-0" />
              <span>Tune pipeline stages and model parameters</span>
            </li>
            <li class="flex items-start gap-3 text-sm text-neutral-600 dark:text-neutral-300">
              <UIcon name="lucide:check" class="size-4 text-brand-500 dark:text-brand-400 mt-0.5 shrink-0" />
              <span>Docker & Kubernetes deployment with full control</span>
            </li>
            <li class="flex items-start gap-3 text-sm text-neutral-600 dark:text-neutral-300">
              <UIcon name="lucide:check" class="size-4 text-brand-500 dark:text-brand-400 mt-0.5 shrink-0" />
              <span>AGPL v3 licensed — fork, modify, contribute</span>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <!-- CTA -->
    <div class="bg-neutral-900 text-white">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 py-20 sm:py-28 text-center">
        <h2 class="text-3xl sm:text-4xl font-bold tracking-tight mb-4">
          Start catching bugs before your users do.
        </h2>
        <p class="text-lg text-neutral-400 max-w-2xl mx-auto mb-10">
          Open source and free to self-host. Deploy in minutes with Docker Compose.
        </p>
        <div class="flex flex-wrap items-center justify-center gap-4">
          <UTooltip text="Coming soon" :delay-duration="0">
            <InspiraShimmerButton background="rgb(6, 72, 60)" class="text-base font-semibold opacity-50 cursor-not-allowed" disabled>
              Get Started
              <UIcon name="lucide:arrow-right" class="size-4 ml-2" />
            </InspiraShimmerButton>
          </UTooltip>
          <UButton
            to="https://github.com/numberly/reviewate"
            target="_blank"
            color="neutral"
            variant="outline"
            size="xl"
            icon="lucide:github"
            label="View on GitHub"
            class="text-white! bg-transparent! ring-neutral-500! hover:bg-white/10!"
          />
        </div>
      </div>
    </div>
  </div>
</template>
