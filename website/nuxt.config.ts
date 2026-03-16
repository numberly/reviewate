import { createRequire } from 'module'
import { readdirSync } from 'fs'
import { join } from 'path'

const require = createRequire(import.meta.url)

// Resolve Vue internal packages to exact paths to prevent duplicate bundling in Workers
const vueInternalAliases = Object.fromEntries(
  ['@vue/runtime-core', '@vue/runtime-dom', '@vue/shared', '@vue/reactivity'].map(
    (pkg) => [pkg, require.resolve(`${pkg}/dist/${pkg.split('/').pop()}.esm-bundler.js`)],
  ),
)

// Scan content directory for sitemap URLs (D1 isn't available at build time)
function getContentUrls(dir: string, prefix: string): string[] {
  const urls: string[] = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) {
      urls.push(...getContentUrls(full, `${prefix}/${entry.name.replace(/^\d+\./, '')}`))
    }
    else if (entry.name.endsWith('.md')) {
      urls.push(`${prefix}/${entry.name.replace(/^\d+\./, '').replace(/\.md$/, '')}`)
    }
  }
  return urls
}

const contentUrls = [
  ...getContentUrls('content/blog', '/blog'),
  ...getContentUrls('content/docs', '/docs'),
]

export default defineNuxtConfig({
  modules: ['@nuxt/ui', '@nuxtjs/sitemap', '@nuxt/content'],

  vite: {
    server: {
      allowedHosts: ['reviewate.com', 'www.reviewate.com'],
    },
    resolve: {
      alias: vueInternalAliases,
    },
  },

  site: {
    url: 'https://reviewate.com',
  },

  sitemap: {
    urls: contentUrls,
  },

  app: {
    head: {
      htmlAttrs: { lang: 'en' },
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { property: 'og:site_name', content: 'Reviewate' },
        { property: 'og:type', content: 'website' },
        { property: 'og:image', content: 'https://reviewate.com/og-image.png' },
        { property: 'og:image:width', content: '1200' },
        { property: 'og:image:height', content: '630' },
      ],
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/logo.svg' },
        { rel: 'icon', type: 'image/png', sizes: '32x32', href: '/favicon-32x32.png' },
        { rel: 'icon', type: 'image/png', sizes: '16x16', href: '/favicon-16x16.png' },
        { rel: 'apple-touch-icon', sizes: '180x180', href: '/apple-touch-icon.png' },
        { rel: 'llms', href: '/llms.txt' },
      ],
    },
  },

  css: ['~/assets/main.css'],

  colorMode: {
    preference: 'system',
  },

  nitro: {
    preset: 'cloudflare-pages',
    cloudflare: {
      nodeCompat: true,
      deployConfig: true,
    },
    prerender: {
      autoSubfolderIndex: false,
      crawlLinks: true,
      routes: ['/', '/blog', '/docs', '/pricing'],
      failOnError: false,
    },
    alias: vueInternalAliases,
  },

  compatibilityDate: '2025-07-15',
})
