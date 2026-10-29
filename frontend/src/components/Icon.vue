<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ name: string; size?: number }>(), { size: 18 })

const paths: Record<string, string> = {
  dashboard: 'M3 3h7v7H3zM14 3h7v4h-7zM14 11h7v10h-7zM3 14h7v7H3z',
  cases: 'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',
  plans: 'M9 4h6v3H9zM7 5H5v15h14V5h-2M9 12h6M9 16h4',
  compare: 'M4 8h11l-3-3M20 16H9l3 3',
  stability: 'M3 12h4l2-6 3 12 2.5-6H21',
  ai: 'M12 3l1.8 4.6L18 9.5l-4.2 1.9L12 16l-1.8-4.6L6 9.5l4.2-1.9zM18.5 15l.9 2.3 2.1.9-2.1.9-.9 2.3-.9-2.3-2.1-.9 2.1-.9z',
  automation: 'M5 5h14v10H5zM9 19h6M12 15v4M9 9l2 2-2 2M13 13h3',
  users: 'M8 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM2.5 20c0-3 2.5-5 5.5-5s5.5 2 5.5 5M17 11.5a2.8 2.8 0 100-5.6M17.5 20c0-2.2-.8-3.7-2-4.6',
  logout: 'M15 17l4-5-4-5M19 12H10M12 4H6a2 2 0 00-2 2v12a2 2 0 002 2h6',
  refresh: 'M20 11a8 8 0 10-2.6 5.9M20 5v6h-6',
}

const d = computed(() => paths[props.name] ?? paths.dashboard)
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.7"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="d" />
  </svg>
</template>
