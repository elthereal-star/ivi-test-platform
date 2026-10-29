<script setup lang="ts">
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{ option: EChartsOption; height?: number }>(), { height: 260 })

const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
let observer: ResizeObserver | null = null

onMounted(() => {
  if (!el.value) return
  chart = echarts.init(el.value)
  chart.setOption(props.option)
  // 侧边栏折叠/窗口变化时容器尺寸会变，靠 ResizeObserver 自动重排
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(el.value)
})

watch(
  () => props.option,
  (opt) => chart?.setOption(opt, true),
  { deep: true },
)

onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div ref="el" :style="{ width: '100%', height: `${height}px` }" />
</template>
