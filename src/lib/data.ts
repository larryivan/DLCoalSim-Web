export type DatasetSummary = {
  id: string;
  name: string;
  n_samples: number;
  n_shards: number;
  sequence_length_bp: number;
  n_haplotypes: number;
  time_bins: number;
  sample_files_human: string;
  hf_repo: string;
  hf_url: string;
  detail_base_url?: string;
  index_path: string;
  detail_path: string;
};

export type DatasetRegistry = {
  generated_at: string;
  datasets: DatasetSummary[];
};

export type CountItem = {
  value: string;
  count: number;
};

export type DatasetDetail = {
  id: string;
  manifest: Record<string, unknown>;
  distributions: Record<string, CountItem[]>;
  numeric_ranges: Record<string, { min: number; max: number }>;
};

export type SampleIndexRow = {
  sample_id: string;
  source_type: string;
  demography_type: string;
  scenario_key: string;
  map_mode: string;
  noise_profile: string;
  n_variants: number;
  Ne_ratio_max_min: number;
  shard_file: string;
  detail_file: string;
  detail_index: number;
};

export type SampleDetailRow = SampleIndexRow & {
  shard_metadata_file: string;
  sample_index_in_shard: number;
  source_type: string;
  sequence_length: number;
  n_haplotypes: number;
  n_diploid_individuals: number;
  variant_density_per_mb: number;
  min_Ne: number;
  max_Ne: number;
  event_severity: number | null;
  event_duration: number | null;
  has_recent_event: boolean;
  has_ancient_event: boolean;
  missing_rate: number;
  genotype_error: number;
  phase_switch_pair_count: number;
  phaseable_pair_count: number;
  mean_obs_rec_rate: number;
  mean_obs_mut_rate: number;
  std_obs_rec_rate: number;
  std_obs_mut_rate: number;
  num_trees: number;
  num_sites: number;
  target_aggregation: string;
  target_scale: string;
  seed: number;
  target_log10_ne: number[];
  target_ne_points: Array<[number, number]>;
  variant_density_preview: Array<[number, number]>;
  rec_map_preview: Array<[number, number]>;
  mut_map_preview: Array<[number, number]>;
  time_span_min: number;
  time_span_max: number;
  hf_shard_url: string;
  hf_metadata_url: string;
};

export async function loadJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.status}`);
  }
  return (await response.json()) as T;
}
