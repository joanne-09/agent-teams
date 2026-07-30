<template>
  <div class="slidev-layout ppt">
    <slot />
  </div>
</template>

<style scoped>
/* PowerPoint-style content layout:
   title at top with a thin rule (title bar),
   body content left-aligned in the left ~64%,
   right side left open for images/diagrams. */
.ppt {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  text-align: left;
  padding-top: 3.6rem !important;
}
.ppt :deep(h1) {
  border-bottom: 1px solid var(--line);
  padding-bottom: 0.55rem;
  margin-bottom: 1.6rem;
}
.ppt :deep(ul),
.ppt :deep(ol) {
  max-width: 64%;
  font-size: 1.2rem;
  line-height: 1.9;
}
.ppt :deep(li) {
  margin-bottom: 0.35rem;
}
.ppt :deep(p) {
  max-width: 64%;
}
</style>
