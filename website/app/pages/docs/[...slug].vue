<script setup lang="ts">
definePageMeta({ layout: 'docs' })

const route = useRoute()

const { data: navigation } = useNuxtData('docs-navigation')

// Flatten the root "Docs" wrapper from the navigation tree
const docsNavigation = computed(() => {
  if (!navigation.value) return []
  if (navigation.value.length === 1 && navigation.value[0]?.children) {
    return navigation.value[0].children
  }
  return navigation.value
})

const { data: page } = await useAsyncData(`docs-${route.path}`, () =>
  queryCollection('docs').path(route.path).first(),
  { watch: [() => route.path] },
)

if (!page.value) {
  throw createError({ statusCode: 404, message: 'Page not found' })
}

const { data: surround } = await useAsyncData(`docs-${route.path}-surround`, () =>
  queryCollectionItemSurroundings('docs', route.path),
  { watch: [() => route.path] },
)

const canonicalUrl = useRequestURL().href

useSeoMeta({
  title: `${page.value.title} - Reviewate Docs`,
  description: page.value.description,
  ogTitle: `${page.value.title} - Reviewate Docs`,
  ogDescription: page.value.description,
  ogImage: 'https://reviewate.com/og-image.png',
  ogUrl: canonicalUrl,
  ogType: 'article',
  twitterCard: 'summary_large_image',
  twitterTitle: `${page.value.title} - Reviewate Docs`,
  twitterDescription: page.value.description,
  twitterImage: 'https://reviewate.com/og-image.png',
})

useHead({
  link: [{ rel: 'canonical', href: canonicalUrl }],
  script: [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'TechArticle',
        'headline': page.value.title,
        'description': page.value.description,
        'publisher': {
          '@type': 'Organization',
          'name': 'Reviewate',
          'url': 'https://reviewate.com',
        },
      }),
    },
  ],
})
</script>

<template>
  <UContainer>
    <UPage>
      <template #left>
        <UPageAside>
          <UContentNavigation :navigation="docsNavigation" highlight />
        </UPageAside>
      </template>

      <UPageBody>
        <UPageHeader :title="page!.title" :description="page!.description" />

        <div class="prose prose-neutral dark:prose-invert max-w-none">
          <ContentRenderer v-if="page" :value="page" />
        </div>

        <UContentSurround :surround="surround!" />
      </UPageBody>

      <template #right>
        <UPageAside>
          <UContentToc :links="page!.body?.toc?.links" highlight />
        </UPageAside>
      </template>
    </UPage>
  </UContainer>
</template>
