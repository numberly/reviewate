<script setup lang="ts">
const canonicalUrl = useRequestURL().href

useSeoMeta({
  title: 'Blog - Reviewate',
  description: 'Updates, tutorials, and insights about AI-powered code review.',
  ogTitle: 'Blog - Reviewate',
  ogDescription: 'Updates, tutorials, and insights about AI-powered code review.',
  ogImage: 'https://reviewate.com/og-image.png',
  ogUrl: canonicalUrl,
  twitterCard: 'summary_large_image',
  twitterTitle: 'Blog - Reviewate',
  twitterDescription: 'Updates, tutorials, and insights about AI-powered code review.',
  twitterImage: 'https://reviewate.com/og-image.png',
})

useHead({
  link: [{ rel: 'canonical', href: canonicalUrl }],
})

const { data: posts } = await useAsyncData('blog', () =>
  queryCollection('blog').order('date', 'DESC').all(),
)
</script>

<template>
  <div>
    <UPageHero
      title="Blog"
      description="Updates, tutorials, and insights about AI-powered code review."
    />

    <UPageSection>
      <UBlogPosts
        v-if="posts?.length"
        :posts="posts.map(post => ({
          title: post.title,
          description: post.description,
          date: new Date(post.date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }),
          badge: post.badge ? { label: post.badge } : undefined,
          to: post.path,
        }))"
      />
      <div v-else class="text-center py-12 text-neutral-500">
        No posts yet. Check back soon!
      </div>
    </UPageSection>
  </div>
</template>
