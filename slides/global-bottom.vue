<template>
  <!-- Page number on every slide but the cover. Rendered by Slidev's
       global-bottom layer, so it survives layout changes and export. -->
  <footer v-if="$slidev.nav.currentPage > 1" class="page-num">
    <span class="page-label">p.</span>{{ $slidev.nav.currentPage }}<span class="page-total"> / {{ $slidev.nav.total }}</span>
  </footer>
</template>

<style scoped>
.page-num {
  position: absolute;
  right: 1.5rem;
  bottom: 0.95rem;
  z-index: 20;
  color: var(--muted);
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.06em;
}
.page-label { opacity: 0.55; margin-right: 0.15em; }
.page-total { opacity: 0.6; }
</style>
