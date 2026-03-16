<script setup lang="ts">
const route = useRoute()

const { data: post } = await useAsyncData(route.path, () =>
  queryCollection('blog').path(route.path).first(),
)

if (!post.value) {
  throw createError({ statusCode: 404, message: 'Post not found' })
}

const canonicalUrl = useRequestURL().href

useSeoMeta({
  title: `${post.value.title} - Reviewate Blog`,
  description: post.value.description,
  ogTitle: `${post.value.title} - Reviewate Blog`,
  ogDescription: post.value.description,
  ogImage: 'https://reviewate.com/og-image.png',
  ogUrl: canonicalUrl,
  ogType: 'article',
  twitterCard: 'summary_large_image',
  twitterTitle: `${post.value.title} - Reviewate Blog`,
  twitterDescription: post.value.description,
  twitterImage: 'https://reviewate.com/og-image.png',
})

useHead({
  link: [{ rel: 'canonical', href: canonicalUrl }],
  script: [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'Article',
        'headline': post.value.title,
        'description': post.value.description,
        'datePublished': post.value.date,
        'dateModified': post.value.date,
        'author': {
          '@type': 'Organization',
          'name': 'Reviewate Team',
          'url': 'https://reviewate.com',
        },
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
  <div>
    <UPageHero
      :title="post!.title"
      :description="post!.description"
    >
      <template #headline>
        <UBadge v-if="post!.badge" variant="outline" :label="post!.badge" />
      </template>
    </UPageHero>

    <UPageSection>
      <div class="prose prose-neutral dark:prose-invert max-w-3xl mx-auto">
        <ContentRenderer v-if="post" :value="post" />
      </div>
    </UPageSection>
  </div>
</template>
