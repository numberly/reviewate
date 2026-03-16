# Website

Marketing & landing page built with Nuxt 4, Nuxt UI, and Nuxt Content.

## Structure

- `app/pages/` - File-based routing (index, pricing, blog)
- `app/components/` - Vue components (hero animations, pipeline viz, demos)
- `app/components/inspira/` - Reusable animated UI primitives (beams, glare cards, shimmer buttons, etc.)
- `app/layouts/` - Default layout with header, `<main>`, and footer
- `content/blog/` - Markdown blog posts (powered by @nuxt/content)
- `public/` - Static assets (logo, og-image, llms.txt)

## Key Modules

- `@nuxt/ui` v4 - Component library and theming
- `@nuxt/content` - Blog posts from Markdown files
- `@nuxtjs/sitemap` - Auto-generated sitemap and robots.txt in production
- `motion-v` - Animations (used in inspira components)

## SEO

- Canonical URLs and OG meta on every page via `useSeoMeta()` + `useHead()`
- JSON-LD structured data: `WebSite` + `SoftwareApplication` on homepage, `Article` on blog posts
- Global `og:site_name` and `og:type` in `nuxt.config.ts`
- `public/llms.txt` for AI crawler discoverability

## Commands

- `pnpm dev` - Start dev server
- `pnpm build` - Build for production
- `pnpm generate` - Static site generation
- `pnpm preview` - Preview production build
