<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ArrowLeft, ChevronsLeft, ChevronsRight, Copy, Database, ExternalLink, FileJson, Layers, Menu, Search, SlidersHorizontal, Table2, X } from "lucide-vue-next";
import EChartDistributionPie from "./components/EChartDistributionPie.vue";
import EChartLine from "./components/EChartLine.vue";
import { loadJson, type CountItem, type DatasetDetail, type DatasetRegistry, type DatasetSummary, type SampleDetailRow, type SampleIndexRow } from "./lib/data";

type Point = [number, number];
type FilterField = "demography_type" | "map_mode" | "noise_profile";
type SortKey = "sample_id" | "demography_type" | "map_mode" | "noise_profile" | "n_variants" | "Ne_ratio_max_min";
type SortDirection = "asc" | "desc";

const filterFields: Array<{ key: FilterField; label: string }> = [
  { key: "demography_type", label: "demography_type" },
  { key: "map_mode", label: "map_mode" },
  { key: "noise_profile", label: "noise_profile" },
];
const sortKeys: SortKey[] = ["sample_id", "demography_type", "map_mode", "noise_profile", "n_variants", "Ne_ratio_max_min"];
const filterQueryKeys: Record<FilterField, string> = {
  demography_type: "demo",
  map_mode: "map",
  noise_profile: "noise",
};

const registry = ref<DatasetRegistry | null>(null);
const dataset = ref<DatasetSummary | null>(null);
const detail = ref<DatasetDetail | null>(null);
const samples = ref<SampleIndexRow[]>([]);
const selectedSample = ref<SampleDetailRow | null>(null);
const loading = ref(true);
const detailLoading = ref(false);
const error = ref("");
const page = ref(1);
const sidebarCollapsed = ref(false);
const mobileNavOpen = ref(false);
const filtersExpanded = ref(false);
const searchQuery = ref("");
const sortKey = ref<SortKey>("sample_id");
const sortDirection = ref<SortDirection>("asc");
const urlSyncReady = ref(false);
const copyOk = ref(false);
const filters = ref<Record<FilterField, string[]>>({
  demography_type: [],
  map_mode: [],
  noise_profile: [],
});
const pageSize = 50;
const detailCache = new Map<string, SampleDetailRow[]>();
let routeApplying = false;

const filteredSamples = computed(() =>
  samples.value.filter((sample) => {
    const query = searchQuery.value.trim().toLowerCase();
    const passesFilters = filterFields.every(({ key }) => {
      const selected = filters.value[key];
      return selected.length === 0 || selected.includes(String(sample[key] ?? ""));
    });
    if (!passesFilters) return false;
    if (!query) return true;
    return [
      sample.sample_id,
      sample.demography_type,
      sample.map_mode,
      sample.noise_profile,
      sample.scenario_key,
      sample.shard_file,
    ].some((value) => String(value ?? "").toLowerCase().includes(query));
  }),
);

const sortedSamples = computed(() => {
  const rows = [...filteredSamples.value];
  const key = sortKey.value;
  const direction = sortDirection.value === "asc" ? 1 : -1;
  rows.sort((a, b) => {
    const av = a[key];
    const bv = b[key];
    if (typeof av === "number" && typeof bv === "number") return (av - bv) * direction;
    return String(av ?? "").localeCompare(String(bv ?? ""), undefined, { numeric: true, sensitivity: "base" }) * direction;
  });
  return rows;
});

const totalPages = computed(() => Math.max(1, Math.ceil(sortedSamples.value.length / pageSize)));
const pageRows = computed(() => {
  const start = (page.value - 1) * pageSize;
  return sortedSamples.value.slice(start, start + pageSize);
});

const activeFilterCount = computed(() => filterFields.reduce((acc, { key }) => acc + filters.value[key].length, 0));
const activeFilterChips = computed(() =>
  filterFields.flatMap(({ key, label }) => filters.value[key].map((value) => ({ key, label, value }))),
);

const selectedSampleIndex = computed(() => {
  const sample = selectedSample.value;
  if (!sample) return -1;
  return sortedSamples.value.findIndex((row) => row.sample_id === sample.sample_id);
});
const canOpenPrevious = computed(() => selectedSampleIndex.value > 0);
const canOpenNext = computed(() => selectedSampleIndex.value >= 0 && selectedSampleIndex.value < sortedSamples.value.length - 1);

const filterOptions = computed(() => {
  const result = {} as Record<FilterField, Array<{ value: string; count: number }>>;
  for (const { key } of filterFields) {
    const counts = new Map<string, number>();
    for (const sample of samples.value) {
      const value = String(sample[key] ?? "");
      counts.set(value, (counts.get(value) ?? 0) + 1);
    }
    result[key] = Array.from(counts.entries())
      .map(([value, count]) => ({ value, count }))
      .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value));
  }
  return result;
});

const visibleDistributions = computed(() => {
  const result = {} as Record<FilterField, CountItem[]>;
  for (const { key } of filterFields) {
    const counts = new Map<string, number>();
    for (const sample of filteredSamples.value) {
      const value = String(sample[key] ?? "");
      counts.set(value, (counts.get(value) ?? 0) + 1);
    }
    result[key] = Array.from(counts.entries())
      .map(([value, count]) => ({ value, count }))
      .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value));
  }
  return result;
});

const sampleSummaryCards = computed(() => {
  const s = selectedSample.value;
  if (!s) return [];
  return [
    { label: "Variants", value: formatNumber(s.n_variants), sub: `${formatNumber(s.variant_density_per_mb, 1)} / Mb` },
    { label: "Ne ratio", value: formatNumber(s.Ne_ratio_max_min, 2), sub: `${formatNumber(s.min_Ne)}-${formatNumber(s.max_Ne)}` },
    { label: "Missing", value: formatNumber(s.missing_rate * 100, 2) + "%", sub: `genotype error ${formatNumber(s.genotype_error * 100, 2)}%` },
    { label: "Phase switches", value: formatNumber(s.phase_switch_pair_count), sub: `${formatNumber(s.phaseable_pair_count)} phaseable pairs` },
    { label: "Mean recomb.", value: formatRate(s.mean_obs_rec_rate), sub: `sd ${formatRate(s.std_obs_rec_rate)}` },
    { label: "Mean mutation", value: formatRate(s.mean_obs_mut_rate), sub: `sd ${formatRate(s.std_obs_mut_rate)}` },
  ];
});

function formatNumber(value: number | null | undefined, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) return "NA";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(value);
}

function formatRate(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "NA";
  return value.toExponential(2);
}

function logSpace(start: number, stop: number, n: number) {
  const a = Math.log(start);
  const b = Math.log(stop);
  return Array.from({ length: n }, (_, i) => Math.exp(a + ((b - a) * i) / Math.max(n - 1, 1)));
}

function targetBinPoints(sample: SampleDetailRow): Point[] {
  const values = sample.target_log10_ne;
  if (values.length === 0) return [];
  const start = Math.max(sample.time_span_min || 50, 1e-9);
  const stop = Math.max(sample.time_span_max || 500000, start * 1.01);
  const edges = logSpace(start, stop, values.length + 1);
  const points: Point[] = [];
  values.forEach((value, i) => {
    const ne = 10 ** value;
    points.push([edges[i], ne], [edges[i + 1], ne]);
  });
  return points;
}

function mapStepPoints(points: Point[], sequenceLength: number): Point[] {
  if (points.length === 0) return [];
  const endMb = sequenceLength / 1_000_000;
  const result = points.slice();
  const last = result[result.length - 1];
  if (last && last[0] < endMb) result.push([endMb, last[1]]);
  return result;
}

function emptyFilters(): Record<FilterField, string[]> {
  return {
    demography_type: [],
    map_mode: [],
    noise_profile: [],
  };
}

function toggleFilter(key: FilterField, value: string) {
  const selected = filters.value[key];
  filters.value[key] = selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value];
  page.value = 1;
}

function clearFilter(key: FilterField) {
  filters.value[key] = [];
  page.value = 1;
}

function clearAllFilters() {
  for (const { key } of filterFields) filters.value[key] = [];
  page.value = 1;
}

function resetBrowserControls() {
  filters.value = emptyFilters();
  searchQuery.value = "";
  sortKey.value = "sample_id";
  sortDirection.value = "asc";
  page.value = 1;
}

function clearSearch() {
  searchQuery.value = "";
  page.value = 1;
}

function setSort(key: SortKey) {
  if (sortKey.value === key) {
    sortDirection.value = sortDirection.value === "asc" ? "desc" : "asc";
  } else {
    sortKey.value = key;
    sortDirection.value = key === "n_variants" || key === "Ne_ratio_max_min" ? "desc" : "asc";
  }
  page.value = 1;
}

function sortIndicator(key: SortKey) {
  if (sortKey.value !== key) return "";
  return sortDirection.value === "asc" ? "↑" : "↓";
}

function handleDistributionSlice(key: FilterField, value: string) {
  if (value === "Other") return;
  toggleFilter(key, value);
  filtersExpanded.value = true;
}

function datasetBadge(name: string) {
  const sizeMatch = name.match(/(\d+)\s*Mb/i);
  if (sizeMatch) return sizeMatch[1];
  const parts = name.split(/[-_\s]+/).filter(Boolean);
  const letters = parts.map((part) => part[0]).join("").slice(0, 2);
  return (letters || name.slice(0, 2)).toUpperCase();
}

function distributionMaxSlices(key: string | number) {
  return String(key) === "demography_type" ? 9 : 6;
}

function distributionHeight(key: string | number) {
  return String(key) === "demography_type" ? 330 : 305;
}

async function openDataset(item: DatasetSummary, options: { resetControls?: boolean } = {}) {
  loading.value = true;
  error.value = "";
  selectedSample.value = null;
  if (dataset.value?.id !== item.id) detailCache.clear();
  if (options.resetControls ?? true) resetBrowserControls();
  mobileNavOpen.value = false;
  dataset.value = item;
  try {
    const base = import.meta.env.BASE_URL;
    const [loadedDetail, loadedSamples] = await Promise.all([
      loadJson<DatasetDetail>(`${base}${item.detail_path}`),
      loadJson<SampleIndexRow[]>(`${base}${item.index_path}`),
    ]);
    detail.value = loadedDetail;
    samples.value = loadedSamples;
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    loading.value = false;
  }
}

function backToRegistry() {
  dataset.value = null;
  detail.value = null;
  samples.value = [];
  selectedSample.value = null;
  resetBrowserControls();
  mobileNavOpen.value = false;
}

async function openSample(row: SampleIndexRow) {
  if (!dataset.value) return;
  detailLoading.value = true;
  error.value = "";
  try {
    const path = `${import.meta.env.BASE_URL}data/${dataset.value.id}/${row.detail_file}`;
    let chunk = detailCache.get(row.detail_file);
    if (!chunk) {
      chunk = await loadJson<SampleDetailRow[]>(path);
      detailCache.set(row.detail_file, chunk);
    }
    selectedSample.value = chunk[row.detail_index];
    if (!routeApplying) window.requestAnimationFrame(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    detailLoading.value = false;
  }
}

async function openSampleById(sampleId: string) {
  const row = samples.value.find((item) => item.sample_id === sampleId);
  if (!row) return;
  const index = sortedSamples.value.findIndex((item) => item.sample_id === sampleId);
  if (index >= 0) page.value = Math.floor(index / pageSize) + 1;
  await openSample(row);
}

function closeSampleDetail() {
  const index = selectedSampleIndex.value;
  if (index >= 0) page.value = Math.floor(index / pageSize) + 1;
  selectedSample.value = null;
}

async function openAdjacentSample(offset: number) {
  const nextIndex = selectedSampleIndex.value + offset;
  const next = sortedSamples.value[nextIndex];
  if (!next) return;
  page.value = Math.floor(nextIndex / pageSize) + 1;
  await openSample(next);
}

async function copySampleId() {
  if (!selectedSample.value) return;
  try {
    await navigator.clipboard.writeText(selectedSample.value.sample_id);
    copyOk.value = true;
    window.setTimeout(() => {
      copyOk.value = false;
    }, 1200);
  } catch {
    copyOk.value = false;
  }
}

const metadataRows = computed(() => {
  const s = selectedSample.value;
  if (!s) return [];
  return [
    ["sample_id", s.sample_id],
    ["source_type", s.source_type],
    ["scenario_key", s.scenario_key],
    ["demography_type", s.demography_type],
    ["map_mode", s.map_mode],
    ["noise_profile", s.noise_profile],
    ["n_variants", formatNumber(s.n_variants)],
    ["variant_density_per_mb", formatNumber(s.variant_density_per_mb, 1)],
    ["Ne_ratio_max_min", formatNumber(s.Ne_ratio_max_min, 2)],
    ["min_Ne", formatNumber(s.min_Ne)],
    ["max_Ne", formatNumber(s.max_Ne)],
    ["missing_rate", formatNumber(s.missing_rate, 4)],
    ["genotype_error", formatNumber(s.genotype_error, 4)],
    ["phase_switch_pair_count", formatNumber(s.phase_switch_pair_count)],
    ["mean_obs_rec_rate", formatRate(s.mean_obs_rec_rate)],
    ["mean_obs_mut_rate", formatRate(s.mean_obs_mut_rate)],
    ["time_span_min", formatNumber(s.time_span_min)],
    ["time_span_max", formatNumber(s.time_span_max)],
    ["target bins", String(s.target_log10_ne.length)],
    ["shard_file", s.shard_file],
    ["sample_index_in_shard", String(s.sample_index_in_shard)],
  ];
});

function routeValues(params: URLSearchParams, key: string) {
  return (params.get(key) ?? "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

function isSortKey(value: string | null): value is SortKey {
  return !!value && sortKeys.includes(value as SortKey);
}

function readRouteState() {
  const params = new URLSearchParams(window.location.search);
  const nextFilters = emptyFilters();
  for (const { key } of filterFields) {
    nextFilters[key] = routeValues(params, filterQueryKeys[key]);
  }
  return {
    datasetId: params.get("dataset") || params.get("d") || "",
    sampleId: params.get("sample") || "",
    query: params.get("q") || "",
    page: Math.max(1, Number(params.get("page") || 1) || 1),
    sort: isSortKey(params.get("sort")) ? params.get("sort") as SortKey : "sample_id",
    direction: params.get("dir") === "desc" ? "desc" as SortDirection : "asc" as SortDirection,
    filters: nextFilters,
  };
}

function applyRouteControls(route: ReturnType<typeof readRouteState>) {
  searchQuery.value = route.query;
  sortKey.value = route.sort;
  sortDirection.value = route.direction;
  filters.value = route.filters;
  filtersExpanded.value = activeFilterCount.value > 0;
  page.value = Math.min(route.page, totalPages.value);
}

function writeRouteState() {
  if (!urlSyncReady.value || routeApplying) return;
  const params = new URLSearchParams();
  if (dataset.value) params.set("dataset", dataset.value.id);
  if (selectedSample.value) params.set("sample", selectedSample.value.sample_id);
  if (searchQuery.value.trim()) params.set("q", searchQuery.value.trim());
  if (page.value > 1 && !selectedSample.value) params.set("page", String(page.value));
  if (sortKey.value !== "sample_id") params.set("sort", sortKey.value);
  if (sortDirection.value !== "asc") params.set("dir", sortDirection.value);
  for (const { key } of filterFields) {
    const selected = filters.value[key];
    if (selected.length) params.set(filterQueryKeys[key], selected.join(","));
  }
  const query = params.toString();
  const next = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
  if (next !== `${window.location.pathname}${window.location.search}${window.location.hash}`) {
    window.history.replaceState(null, "", next);
  }
}

async function applyRouteState() {
  if (!registry.value) return;
  const route = readRouteState();
  routeApplying = true;
  try {
    if (!route.datasetId) {
      dataset.value = null;
      detail.value = null;
      samples.value = [];
      selectedSample.value = null;
      resetBrowserControls();
      return;
    }

    const item = registry.value.datasets.find((entry) => entry.id === route.datasetId || entry.name === route.datasetId);
    if (!item) return;
    if (dataset.value?.id !== item.id) await openDataset(item, { resetControls: false });
    applyRouteControls(route);
    if (route.sampleId) await openSampleById(route.sampleId);
    else selectedSample.value = null;
  } finally {
    routeApplying = false;
  }
}

function handlePopState() {
  void applyRouteState();
}

watch(searchQuery, () => {
  if (!routeApplying) page.value = 1;
});

watch(totalPages, () => {
  if (page.value > totalPages.value) page.value = totalPages.value;
});

watch(
  () => [
    dataset.value?.id ?? "",
    selectedSample.value?.sample_id ?? "",
    page.value,
    searchQuery.value,
    sortKey.value,
    sortDirection.value,
    filterFields.map(({ key }) => filters.value[key].join("\u001f")).join("\u001e"),
  ],
  writeRouteState,
);

onMounted(async () => {
  loading.value = true;
  try {
    registry.value = await loadJson<DatasetRegistry>(`${import.meta.env.BASE_URL}data/registry.json`);
    await applyRouteState();
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    loading.value = false;
    urlSyncReady.value = true;
    writeRouteState();
  }
  window.addEventListener("popstate", handlePopState);
});

onBeforeUnmount(() => {
  window.removeEventListener("popstate", handlePopState);
});
</script>

<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed, 'mobile-nav-open': mobileNavOpen }">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">
          <Database :size="18" />
        </div>
        <div class="brand-copy">
          <strong>DLCoalSim</strong>
          <span>Data Portal</span>
        </div>
        <button
          class="sidebar-toggle desktop-sidebar-toggle"
          type="button"
          :title="sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
          :aria-label="sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
          @click="sidebarCollapsed = !sidebarCollapsed"
        >
          <ChevronsRight v-if="sidebarCollapsed" :size="15" />
          <ChevronsLeft v-else :size="15" />
        </button>
        <button
          class="sidebar-toggle mobile-sidebar-toggle"
          type="button"
          :title="mobileNavOpen ? 'Close datasets' : 'Open datasets'"
          :aria-label="mobileNavOpen ? 'Close datasets' : 'Open datasets'"
          @click="mobileNavOpen = !mobileNavOpen"
        >
          <X v-if="mobileNavOpen" :size="16" />
          <Menu v-else :size="16" />
        </button>
      </div>

      <div class="sidebar-section">
        <div class="sidebar-label">Datasets</div>
        <button
          v-for="item in registry?.datasets"
          :key="item.id"
          class="dataset-nav-item"
          :class="{ active: dataset?.id === item.id }"
          :title="item.name"
          :aria-label="item.name"
          type="button"
          @click="openDataset(item)"
        >
          <span class="dataset-badge">{{ datasetBadge(item.name) }}</span>
          <span class="dataset-copy">
            <strong>{{ item.name }}</strong>
            <small>{{ formatNumber(item.n_samples) }} samples · {{ item.sample_files_human }}</small>
          </span>
        </button>
      </div>

      <div class="sidebar-foot">
        <span>Static registry</span>
        <span v-if="registry">{{ registry.generated_at.slice(0, 10) }}</span>
      </div>
    </aside>

    <main class="workspace">
      <header class="workspace-header">
        <div>
          <p class="eyebrow">{{ dataset ? "Dataset Workspace" : "Dataset Registry" }}</p>
          <h1>{{ dataset ? dataset.name : "Available Datasets" }}</h1>
          <p class="subtitle">
            {{ dataset ? "Browse sample annotations, preview simulated observations, and locate raw shards." : "Select a hosted DLCoalSim dataset to inspect its sample corpus." }}
          </p>
        </div>
        <div class="header-actions">
          <button v-if="dataset" class="secondary-button" type="button" @click="backToRegistry">
            <ArrowLeft :size="16" />
            Registry
          </button>
          <a v-if="dataset" class="primary-link" :href="dataset.hf_url" target="_blank" rel="noreferrer">
            <ExternalLink :size="16" />
            Hugging Face
          </a>
        </div>
      </header>

      <p v-if="error" class="state-message error">{{ error }}</p>
      <p v-else-if="loading" class="state-message">Loading data index...</p>

      <section v-else-if="!dataset" class="registry-list">
        <article v-for="item in registry?.datasets" :key="item.id" class="registry-row" @click="openDataset(item)">
          <div class="registry-row-main">
            <Database :size="18" />
            <div>
              <h2>{{ item.name }}</h2>
              <p>{{ item.hf_repo }}</p>
            </div>
          </div>
          <dl class="registry-metrics">
            <div><dt>Samples</dt><dd>{{ formatNumber(item.n_samples) }}</dd></div>
            <div><dt>Shards</dt><dd>{{ formatNumber(item.n_shards) }}</dd></div>
            <div><dt>Sequence</dt><dd>{{ formatNumber(item.sequence_length_bp / 1_000_000) }} Mb</dd></div>
            <div><dt>Size</dt><dd>{{ item.sample_files_human }}</dd></div>
          </dl>
        </article>
      </section>

      <template v-else>
        <section class="kpi-strip">
          <div class="kpi">
            <Layers :size="16" />
            <span>Samples</span>
            <strong>{{ formatNumber(dataset.n_samples) }}</strong>
          </div>
          <div class="kpi">
            <Table2 :size="16" />
            <span>Shards</span>
            <strong>{{ formatNumber(dataset.n_shards) }}</strong>
          </div>
          <div class="kpi">
            <FileJson :size="16" />
            <span>Time bins</span>
            <strong>{{ formatNumber(dataset.time_bins) }}</strong>
          </div>
          <div class="kpi">
            <Database :size="16" />
            <span>Sequence</span>
            <strong>{{ formatNumber(dataset.sequence_length_bp / 1_000_000) }} Mb</strong>
          </div>
        </section>

        <section v-if="detail && !selectedSample" class="distribution-grid">
          <div v-for="field in filterFields" :key="field.key" class="panel distribution-panel">
            <EChartDistributionPie
              :title="field.label"
              :items="visibleDistributions[field.key]"
              :total="filteredSamples.length"
              :max-slices="distributionMaxSlices(field.key)"
              :height="distributionHeight(field.key)"
              @slice-click="handleDistributionSlice(field.key, $event)"
            />
          </div>
        </section>

        <section v-if="!selectedSample" class="filter-panel">
          <div class="filter-head">
            <div>
              <h2>Sample Browser</h2>
              <p>{{ formatNumber(filteredSamples.length) }} matching records from {{ formatNumber(samples.length) }}</p>
            </div>
            <div class="filter-actions">
              <button class="secondary-button" type="button" @click="filtersExpanded = !filtersExpanded">
                <SlidersHorizontal :size="15" />
                Filters
                <strong v-if="activeFilterCount">{{ activeFilterCount }}</strong>
              </button>
              <button class="secondary-button" type="button" :disabled="activeFilterCount === 0 && !searchQuery" @click="resetBrowserControls">
                Clear
              </button>
            </div>
          </div>
          <div class="browser-toolbar">
            <label class="search-box">
              <Search :size="15" />
              <input v-model="searchQuery" type="search" placeholder="Search sample_id, demography, map, noise, shard..." />
              <button v-if="searchQuery" type="button" aria-label="Clear search" @click="clearSearch">
                <X :size="14" />
              </button>
            </label>
            <div class="sort-pill">
              Sorted by <strong>{{ sortKey }}</strong> {{ sortDirection === "asc" ? "ascending" : "descending" }}
            </div>
          </div>
          <div v-if="activeFilterChips.length" class="active-chips">
            <button v-for="chip in activeFilterChips" :key="`${chip.key}-${chip.value}`" type="button" @click="toggleFilter(chip.key, chip.value)">
              <span>{{ chip.label }}</span>
              {{ chip.value }}
              <X :size="13" />
            </button>
          </div>
          <div v-show="filtersExpanded" class="filter-grid">
            <section v-for="field in filterFields" :key="field.key" class="filter-group">
              <div class="filter-group-head">
                <strong>{{ field.label }}</strong>
                <button v-if="filters[field.key].length" type="button" @click="clearFilter(field.key)">Clear</button>
              </div>
              <div class="filter-options">
                <label v-for="option in filterOptions[field.key]" :key="option.value" class="filter-option">
                  <input
                    type="checkbox"
                    :checked="filters[field.key].includes(option.value)"
                    @change="toggleFilter(field.key, option.value)"
                  />
                  <span>{{ option.value }}</span>
                  <em>{{ formatNumber(option.count) }}</em>
                </label>
              </div>
            </section>
          </div>
        </section>

        <section v-if="!selectedSample" class="table-panel">
          <div class="table-head">
            <div>
              <h2>Sample Records</h2>
              <p>{{ formatNumber(filteredSamples.length) }} indexed records · click a row to open sample detail</p>
            </div>
            <div class="pager">
              <button :disabled="page === 1" @click="page--">Previous</button>
              <span>{{ page }} / {{ totalPages }}</span>
              <button :disabled="page === totalPages" @click="page++">Next</button>
            </div>
          </div>
          <p v-if="sortedSamples.length === 0" class="empty-records">No samples match the current search and filters.</p>
          <template v-else>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th><button class="sort-button" type="button" @click="setSort('sample_id')">sample_id <span>{{ sortIndicator("sample_id") }}</span></button></th>
                  <th><button class="sort-button" type="button" @click="setSort('demography_type')">demography <span>{{ sortIndicator("demography_type") }}</span></button></th>
                  <th><button class="sort-button" type="button" @click="setSort('map_mode')">map <span>{{ sortIndicator("map_mode") }}</span></button></th>
                  <th><button class="sort-button" type="button" @click="setSort('noise_profile')">noise <span>{{ sortIndicator("noise_profile") }}</span></button></th>
                  <th class="numeric"><button class="sort-button numeric" type="button" @click="setSort('n_variants')">variants <span>{{ sortIndicator("n_variants") }}</span></button></th>
                  <th class="numeric"><button class="sort-button numeric" type="button" @click="setSort('Ne_ratio_max_min')">Ne ratio <span>{{ sortIndicator("Ne_ratio_max_min") }}</span></button></th>
                  <th>shard</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="sample in pageRows" :key="sample.sample_id" @click="openSample(sample)">
                  <td class="mono strong">{{ sample.sample_id }}</td>
                  <td><span class="tag">{{ sample.demography_type }}</span></td>
                  <td>{{ sample.map_mode }}</td>
                  <td>{{ sample.noise_profile }}</td>
                  <td class="numeric">{{ formatNumber(sample.n_variants) }}</td>
                  <td class="numeric">{{ formatNumber(sample.Ne_ratio_max_min, 2) }}</td>
                  <td class="mono muted">{{ sample.shard_file }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="sample-card-list">
            <article v-for="sample in pageRows" :key="sample.sample_id" class="sample-card" @click="openSample(sample)">
              <div class="sample-card-head">
                <strong class="mono">{{ sample.sample_id }}</strong>
                <span>{{ formatNumber(sample.n_variants) }} variants</span>
              </div>
              <dl>
                <div><dt>demography</dt><dd>{{ sample.demography_type }}</dd></div>
                <div><dt>map</dt><dd>{{ sample.map_mode }}</dd></div>
                <div><dt>noise</dt><dd>{{ sample.noise_profile }}</dd></div>
                <div><dt>Ne ratio</dt><dd>{{ formatNumber(sample.Ne_ratio_max_min, 2) }}</dd></div>
              </dl>
              <p class="mono">{{ sample.shard_file }}</p>
            </article>
          </div>
          </template>
        </section>

        <p v-else-if="detailLoading" class="state-message">Loading sample detail...</p>

        <section v-else class="record-view">
          <header class="record-header">
            <button class="secondary-button" type="button" @click="closeSampleDetail">
              <ArrowLeft :size="16" />
              Result set
            </button>
            <div>
              <p class="eyebrow">Sample Record</p>
              <h2>{{ selectedSample.sample_id }}</h2>
              <div class="record-tags">
                <span>{{ selectedSample.demography_type }}</span>
                <span>{{ selectedSample.map_mode }}</span>
                <span>{{ selectedSample.noise_profile }}</span>
              </div>
            </div>
            <div class="record-actions">
              <button class="secondary-button" type="button" :disabled="!canOpenPrevious" @click="openAdjacentSample(-1)">Previous</button>
              <button class="secondary-button" type="button" :disabled="!canOpenNext" @click="openAdjacentSample(1)">Next</button>
              <button class="secondary-button" type="button" @click="copySampleId">
                <Copy :size="15" />
                {{ copyOk ? "Copied" : "Copy ID" }}
              </button>
            </div>
          </header>

          <section class="sample-summary-strip">
            <div v-for="card in sampleSummaryCards" :key="card.label" class="sample-summary-card">
              <span>{{ card.label }}</span>
              <strong>{{ card.value }}</strong>
              <small>{{ card.sub }}</small>
            </div>
          </section>

          <div class="record-grid">
            <div class="record-main">
              <div class="panel chart-panel wide-chart">
                <EChartLine
                  title="Target Ne(t), 64 log-time bins"
                  :points="targetBinPoints(selectedSample)"
                  series-name="Ne"
                  x-name="Generations ago"
                  y-name="Ne"
                  x-type="log"
                  y-type="log"
                  color="#285f8f"
                  :height="360"
                  :show-symbols="false"
                />
              </div>

              <div class="chart-grid">
                <div class="panel chart-panel density-chart">
                  <EChartLine
                    title="Variant density, 64 genomic windows"
                    :points="selectedSample.variant_density_preview"
                    series-name="variants/Mb"
                    x-name="Position (Mb)"
                    y-name="variants/Mb"
                    color="#5e6b43"
                    series-type="bar"
                    variant="compact"
                    :height="210"
                  />
                </div>
                <div class="panel chart-panel">
                  <EChartLine
                    title="Observed recombination rate"
                    :points="mapStepPoints(selectedSample.rec_map_preview, selectedSample.sequence_length)"
                    series-name="rate"
                    x-name="Position (Mb)"
                    y-name="rate / bp / generation"
                    y-type="log"
                    step
                    color="#48648c"
                    variant="compact"
                    :height="260"
                    :show-symbols="false"
                  />
                </div>
                <div class="panel chart-panel">
                  <EChartLine
                    title="Observed mutation rate"
                    :points="mapStepPoints(selectedSample.mut_map_preview, selectedSample.sequence_length)"
                    series-name="rate"
                    x-name="Position (Mb)"
                    y-name="rate / bp / generation"
                    y-type="log"
                    step
                    color="#8a5964"
                    variant="compact"
                    :height="260"
                    :show-symbols="false"
                  />
                </div>
              </div>

              <div class="panel link-panel">
                <h2>Raw Data Location</h2>
                <div class="link-grid">
                  <a :href="selectedSample.hf_shard_url" target="_blank" rel="noreferrer">Shard NPZ</a>
                  <a :href="selectedSample.hf_metadata_url" target="_blank" rel="noreferrer">Shard metadata</a>
                </div>
              </div>
            </div>

            <aside class="metadata-panel">
              <h2>Record Metadata</h2>
              <dl>
                <div v-for="[key, value] in metadataRows" :key="key">
                  <dt>{{ key }}</dt>
                  <dd>{{ value }}</dd>
                </div>
              </dl>
            </aside>
          </div>
        </section>
      </template>
    </main>
  </div>
</template>
