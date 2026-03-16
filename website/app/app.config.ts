export default defineAppConfig({
  ui: {
    contentToc: {
      slots: {
        linkText: 'text-wrap',
      },
    },
    button: {
      variants: {
        size: {
          xl: {
            base: 'px-6 py-3 text-base gap-2',
            leadingIcon: 'size-5',
            trailingIcon: 'size-5',
          },
        },
      },
    },
  },
})
