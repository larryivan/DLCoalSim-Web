<script setup lang="ts">
import * as echarts from "echarts";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

type CountItem = {
  value: string;
  count: number;
};

const props = withDefaults(
  defineProps<{
    title: string;
    items: CountItem[];
    total?: number;
    maxSlices?: number;
    height?: number;
  }>(),
  {
    total: undefined,
    maxSlices: 8,
    height: 230,
  },
);
const emit = defineEmits<{
  "slice-click": [value: string];
}>();

const palette = ["#4d6f95", "#6f8fb0", "#527f78", "#8a7aa2", "#9a7561", "#6c7d4f", "#9a6c7a", "#74828d", "#b6c4d0"];
const el = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

const chartRows = computed(() => {
  const rows = props.items.filter((item) => item.count > 0);
  if (rows.length <= props.maxSlices) return rows;
  const head = rows.slice(0, Math.max(props.maxSlices - 1, 1));
  const other = rows.slice(head.length).reduce((acc, item) => acc + item.count, 0);
  return [...head, { value: "Other", count: other }];
});

const totalCount = computed(() => props.total ?? props.items.reduce((acc, item) => acc + item.count, 0));

const legendRows = computed(() =>
  chartRows.value.map((item, index) => ({
    ...item,
    color: palette[index % palette.length],
    percent: totalCount.value > 0 ? (item.count / totalCount.value) * 100 : 0,
  })),
);

function fmt(value: number) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value);
}

function shortLabel(value: string, max = 22) {
  return value.length > max ? `${value.slice(0, max - 3)}...` : value;
}

function renderChart() {
  if (!el.value) return;
  const { width, height } = el.value.getBoundingClientRect();
  if (width < 20 || height < 20) {
    requestAnimationFrame(renderChart);
    return;
  }
  if (!chart) {
    chart = echarts.init(el.value, null, {
      renderer: "canvas",
      devicePixelRatio: window.devicePixelRatio || 1,
    });
    chart.on("click", (params) => {
      if (params.componentType === "series" && typeof params.name === "string") emit("slice-click", params.name);
    });
  }

  const total = props.total ?? props.items.reduce((acc, item) => acc + item.count, 0);
  const data = chartRows.value.map((item) => ({
    name: item.value,
    value: item.count,
  }));

  chart.setOption(
    {
      animationDuration: 300,
      color: palette,
      tooltip: {
        trigger: "item",
        appendToBody: true,
        confine: true,
        backgroundColor: "rgba(18, 28, 24, 0.92)",
        borderWidth: 0,
        extraCssText: "max-width: 320px; white-space: normal; word-break: break-word;",
        textStyle: { color: "#f8fbf8" },
        formatter: (param: unknown) => {
          const item = param as { name?: string; value?: number; percent?: number };
          return [
            item.name ?? "",
            `count: ${fmt(Number(item.value ?? 0))}`,
            `share: ${fmt(Number(item.percent ?? 0))}%`,
          ].join("<br/>");
        },
      },
      graphic: [
        {
          type: "text",
          left: "center",
          top: "middle",
          style: {
            text: "Share",
            fill: "#7a8997",
            fontSize: 11,
            fontWeight: 650,
            textAlign: "center",
          },
        },
      ],
      series: [
        {
          name: props.title,
          type: "pie",
          radius: ["48%", "84%"],
          center: ["50%", "50%"],
          cursor: "pointer",
          minAngle: 2,
          avoidLabelOverlap: true,
          stillShowZeroSum: false,
          itemStyle: {
            borderColor: "#fff",
            borderWidth: 2,
          },
          label: { show: false },
          labelLine: { show: false },
          data,
        },
      ],
    },
    true,
  );
}

function resizeChart() {
  chart?.resize();
  void nextTick(renderChart);
}

watch(
  () => [props.items, props.total, props.maxSlices, props.height],
  () => void nextTick(renderChart),
  { deep: true },
);

onMounted(() => {
  void nextTick(renderChart);
  if (el.value) {
    resizeObserver = new ResizeObserver(() => resizeChart());
    resizeObserver.observe(el.value);
  }
  window.addEventListener("resize", resizeChart);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeChart);
  resizeObserver?.disconnect();
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div class="chart-card distribution-chart-card">
    <div class="chart-title">{{ title }}</div>
    <div v-if="chartRows.length === 0" class="empty-chart">No distribution data</div>
    <div v-else class="distribution-body" :style="{ height: `${height}px` }">
      <div ref="el" class="chart-box distribution-chart-box" />
      <div class="distribution-legend">
        <div
          v-for="row in legendRows"
          :key="row.value"
          class="distribution-legend-row"
          :class="{ disabled: row.value === 'Other' }"
          :title="`${row.value}: ${fmt(row.count)} (${row.percent.toFixed(1)}%)`"
          role="button"
          tabindex="0"
          @click="row.value !== 'Other' && emit('slice-click', row.value)"
          @keydown.enter="row.value !== 'Other' && emit('slice-click', row.value)"
        >
          <span class="distribution-swatch" :style="{ background: row.color }" />
          <span class="distribution-label">{{ shortLabel(row.value, 34) }}</span>
          <strong>{{ row.percent.toFixed(1) }}%</strong>
        </div>
      </div>
    </div>
  </div>
</template>
