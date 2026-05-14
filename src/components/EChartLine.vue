<script setup lang="ts">
import * as echarts from "echarts";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

type AxisType = "value" | "log";
type ChartVariant = "full" | "compact";
type SeriesType = "line" | "bar";
type Point = [number, number];

const props = withDefaults(
  defineProps<{
    title: string;
    points: Point[];
    seriesName?: string;
    xName: string;
    yName: string;
    xType?: AxisType;
    yType?: AxisType;
    step?: boolean;
    color?: string;
    height?: number;
    variant?: ChartVariant;
    seriesType?: SeriesType;
    showSymbols?: boolean;
    showToolbox?: boolean;
    showDataZoom?: boolean;
  }>(),
  {
    seriesName: "value",
    xType: "value",
    yType: "value",
    step: false,
    color: "#2f7d6d",
    height: 280,
    variant: "full",
    seriesType: "line",
    showSymbols: undefined,
    showToolbox: false,
    showDataZoom: false,
  },
);

const el = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

function fmt(value: number) {
  if (!Number.isFinite(value)) return "NA";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value / 1_000_000)}M`;
  if (abs >= 1_000) return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value / 1_000)}k`;
  if (value !== 0 && abs < 0.01) return value.toExponential(1).replace(".0e", "e");
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
}

function cleanPoints(points: Point[]) {
  return points.filter(([x, y]) => {
    if (!Number.isFinite(x) || !Number.isFinite(y)) return false;
    if (props.xType === "log" && x <= 0) return false;
    if (props.yType === "log" && y <= 0) return false;
    return true;
  });
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
  }
  const data = cleanPoints(props.points);
  const compact = props.variant === "compact";
  const hasZoom = props.showDataZoom && !compact;
  const showSymbols = props.showSymbols ?? (!compact && data.length <= 96);
  const grid = compact
    ? { left: 12, right: 12, top: 18, bottom: 30, containLabel: true }
    : { left: 18, right: 20, top: 26, bottom: hasZoom ? 72 : 48, containLabel: true };
  chart.setOption(
    {
      animationDuration: 300,
      animationEasing: "cubicOut",
      color: [props.color],
      grid,
      tooltip: {
        trigger: "axis",
        axisPointer: { type: props.seriesType === "bar" ? "shadow" : "cross" },
        backgroundColor: "rgba(17, 24, 31, 0.94)",
        borderWidth: 0,
        textStyle: { color: "#f8fafc" },
        formatter: (params: unknown) => {
          const item = Array.isArray(params) ? params[0] : params;
          const value = (item as { value?: Point }).value;
          if (!value) return "";
          return [
            `${props.xName}: ${fmt(value[0])}`,
            `${props.seriesName}: ${fmt(value[1])}`,
          ].join("<br/>");
        },
      },
      toolbox: props.showToolbox
        ? {
            right: 4,
            top: 0,
            itemSize: 14,
            feature: {
              dataZoom: { yAxisIndex: "none" },
              restore: {},
              saveAsImage: { pixelRatio: 2 },
            },
          }
        : undefined,
      xAxis: {
        type: props.xType,
        name: compact ? "" : props.xName,
        nameLocation: "middle",
        nameGap: 30,
        axisLine: { lineStyle: { color: "#9aa8b6" } },
        axisLabel: { color: "#637385", formatter: fmt, hideOverlap: true, fontSize: compact ? 10 : 11 },
        splitLine: { lineStyle: { color: "rgba(99,115,133,0.14)" } },
        minorSplitLine: { show: props.xType === "log", lineStyle: { color: "rgba(99,115,133,0.08)" } },
      },
      yAxis: {
        type: props.yType,
        name: compact ? "" : props.yName,
        nameLocation: "middle",
        nameGap: 48,
        axisLine: { lineStyle: { color: "#9aa8b6" } },
        axisLabel: { color: "#637385", formatter: fmt, hideOverlap: true, fontSize: compact ? 10 : 11 },
        splitLine: { lineStyle: { color: "rgba(99,115,133,0.14)" } },
        minorSplitLine: { show: props.yType === "log", lineStyle: { color: "rgba(99,115,133,0.08)" } },
      },
      dataZoom: hasZoom
        ? [
            { type: "inside", xAxisIndex: 0 },
            {
              type: "slider",
              xAxisIndex: 0,
              bottom: 16,
              height: 18,
              borderColor: "rgba(23,33,43,0.14)",
              backgroundColor: "rgba(255,255,255,0.75)",
              fillerColor: "rgba(47,95,134,0.18)",
              handleStyle: { color: props.color },
            },
          ]
        : undefined,
      series: [
        {
          name: props.seriesName,
          type: props.seriesType,
          data,
          step: props.step ? "end" : false,
          showSymbol: props.seriesType === "line" && showSymbols,
          symbolSize: compact ? 3 : 4,
          barWidth: props.seriesType === "bar" ? "82%" : undefined,
          lineStyle: { width: compact ? 1.8 : 2.2 },
          itemStyle: props.seriesType === "bar" ? { opacity: 0.78 } : undefined,
          emphasis: { focus: "series" },
        },
      ],
    },
    true,
  );
}

function resizeChart() {
  chart?.resize();
}

watch(
  () => [
    props.points,
    props.xType,
    props.yType,
    props.step,
    props.color,
    props.variant,
    props.seriesType,
    props.showSymbols,
    props.showToolbox,
    props.showDataZoom,
  ],
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
  <div class="chart-card">
    <div class="chart-title">{{ title }}</div>
    <div v-if="points.length === 0" class="empty-chart">No preview data</div>
    <div v-else ref="el" class="chart-box" :style="{ height: `${height}px` }" />
  </div>
</template>
