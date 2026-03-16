<template>
  <div class="max-w-2xl mx-auto rounded-2xl bg-neutral-900 border border-neutral-700 shadow-2xl overflow-hidden text-left">
    <!-- Review comment mockup -->
    <div class="p-5 border-b border-neutral-800">
      <div class="flex items-center gap-3 mb-4">
        <div class="size-8 rounded-full bg-white flex items-center justify-center overflow-hidden">
          <img src="/logo.svg" alt="Reviewate" class="size-6" />
        </div>
        <div>
          <span class="text-sm font-medium text-neutral-100">Reviewate</span>
          <span class="text-xs text-neutral-500 ml-2">just now</span>
        </div>
        <span class="ml-auto inline-flex items-center gap-1 rounded-full bg-red-500/15 text-red-400 px-2 py-0.5 text-xs font-medium">
          <UIcon name="lucide:alert-circle" class="size-3" />
          Bug
        </span>
      </div>
      <p class="text-sm text-neutral-300 leading-relaxed">
        <span class="text-neutral-100 font-medium">Potential null reference</span> at line 42.
        <code class="text-brand-300 bg-brand-950 px-1.5 py-0.5 rounded text-xs mx-0.5">user.profile.settings</code>
        can be <code class="text-red-400 bg-red-950 px-1.5 py-0.5 rounded text-xs">undefined</code>
        when the user hasn't completed onboarding. Add a null check before accessing nested properties.
      </p>
    </div>
    <!-- Code snippet -->
    <div class="px-5 py-4 font-mono text-xs">
      <div class="text-neutral-500">
        <span class="text-neutral-600 select-none">42 </span>
        <span class="text-red-400/70 line-through">const theme = user.profile.settings.theme;</span>
      </div>
      <div class="text-neutral-300 mt-1">
        <span class="text-neutral-600 select-none">42 </span>
        <span class="text-green-400">const theme = user.profile?.settings?.theme ?? 'default';</span>
      </div>
    </div>
    <!-- Bottom bar -->
    <div class="flex items-center gap-3 px-5 py-3 bg-neutral-950/50 border-t border-neutral-800">
      <UIcon name="lucide:file-code" class="size-4 text-neutral-500" />
      <span class="text-xs text-neutral-500 font-mono">src/components/Dashboard.tsx</span>

    </div>
  </div>
</template>
