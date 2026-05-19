#!/usr/bin/env python3
import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


KEEP_FIELDS = [
    "sample_id",
    "shard_file",
    "shard_metadata_file",
    "sample_index_in_shard",
    "source_type",
    "demography_type",
    "scenario_key",
    "map_mode",
    "noise_profile",
    "sequence_length",
    "n_haplotypes",
    "n_diploid_individuals",
    "n_variants",
    "variant_density_per_mb",
    "Ne_ratio_max_min",
    "min_Ne",
    "max_Ne",
    "event_severity",
    "event_duration",
    "has_recent_event",
    "has_ancient_event",
    "missing_rate",
    "genotype_error",
    "phase_switch_pair_count",
    "phaseable_pair_count",
    "mean_obs_rec_rate",
    "mean_obs_mut_rate",
    "std_obs_rec_rate",
    "std_obs_mut_rate",
    "num_trees",
    "num_sites",
    "target_aggregation",
    "target_scale",
    "time_span_min",
    "time_span_max",
    "seed",
]

NUMERIC_FIELDS = {
    "sample_index_in_shard",
    "sequence_length",
    "n_haplotypes",
    "n_diploid_individuals",
    "n_variants",
    "variant_density_per_mb",
    "Ne_ratio_max_min",
    "min_Ne",
    "max_Ne",
    "event_severity",
    "event_duration",
    "missing_rate",
    "genotype_error",
    "phase_switch_pair_count",
    "phaseable_pair_count",
    "mean_obs_rec_rate",
    "mean_obs_mut_rate",
    "std_obs_rec_rate",
    "std_obs_mut_rate",
    "num_trees",
    "num_sites",
    "seed",
    "time_span_min",
    "time_span_max",
}

BOOLEAN_FIELDS = {"has_recent_event", "has_ancient_event"}
COUNT_FIELDS = ["source_type", "demography_type", "map_mode", "noise_profile"]
INDEX_FIELDS = [
    "sample_id",
    "source_type",
    "demography_type",
    "scenario_key",
    "map_mode",
    "noise_profile",
    "n_variants",
    "Ne_ratio_max_min",
    "shard_file",
]


def parse_value(key, value):
    if value == "":
        return None if key in NUMERIC_FIELDS else ""
    if key in BOOLEAN_FIELDS:
        return value == "True"
    if key in NUMERIC_FIELDS:
        number = float(value)
        return int(number) if number.is_integer() else number
    return value


def read_metadata(path):
    rows = {}
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item = {key: parse_value(key, row.get(key, "")) for key in KEEP_FIELDS}
            rows[item["sample_id"]] = item
    return rows


def sample_shard_paths(samples_dir):
    def keep(path):
        rel = path.relative_to(samples_dir)
        return not any(part.startswith(".") or part.startswith("_") for part in rel.parts)

    return sorted(
        (path for path in samples_dir.rglob("*.npz") if keep(path)),
        key=lambda path: path.relative_to(samples_dir).as_posix(),
    )


def add_targets(rows, samples_dir):
    for shard_path in sample_shard_paths(samples_dir):
        with np.load(shard_path, allow_pickle=False) as data:
            sample_ids = data["sample_id"].astype(str)
            targets = data["target_log10_ne"]
            var_pos = data["variant_positions_bp"]
            var_offsets = data["variant_offsets"]
            rec_pos = data["obs_rec_pos"]
            rec_pos_offsets = data["obs_rec_pos_offsets"]
            rec_rate = data["obs_rec_rate"]
            rec_rate_offsets = data["obs_rec_rate_offsets"]
            mut_pos = data["obs_mut_pos"]
            mut_pos_offsets = data["obs_mut_pos_offsets"]
            mut_rate = data["obs_mut_rate"]
            mut_rate_offsets = data["obs_mut_rate_offsets"]
            sequence_lengths = data["sequence_length"]
            for i, (sample_id, target) in enumerate(zip(sample_ids, targets)):
                if sample_id in rows:
                    sample = rows[sample_id]
                    seq_len = int(sequence_lengths[i])
                    sample["target_log10_ne"] = np.round(target.astype(float), 5).tolist()
                    sample["target_ne_points"] = target_ne_points(
                        target,
                        sample.get("time_span_min") or 50.0,
                        sample.get("time_span_max") or 500000.0,
                    )
                    positions = var_pos[var_offsets[i] : var_offsets[i + 1]]
                    sample["variant_density_preview"] = variant_density_preview(positions, seq_len)
                    sample["rec_map_preview"] = map_preview(
                        rec_pos[rec_pos_offsets[i] : rec_pos_offsets[i + 1]],
                        rec_rate[rec_rate_offsets[i] : rec_rate_offsets[i + 1]],
                    )
                    sample["mut_map_preview"] = map_preview(
                        mut_pos[mut_pos_offsets[i] : mut_pos_offsets[i + 1]],
                        mut_rate[mut_rate_offsets[i] : mut_rate_offsets[i + 1]],
                    )


def sig(value, digits=5):
    if value is None or not np.isfinite(value):
        return None
    return float(f"{float(value):.{digits}g}")


def target_ne_points(target_log10, time_min, time_max):
    target = np.asarray(target_log10, dtype=float)
    time_min = max(float(time_min), 1e-9)
    time_max = max(float(time_max), time_min * 1.01)
    edges = np.geomspace(time_min, time_max, target.size + 1)
    mids = np.sqrt(edges[:-1] * edges[1:])
    ne = np.power(10.0, target)
    return [[sig(x, 6), sig(y, 6)] for x, y in zip(mids, ne) if y > 0]


def variant_density_preview(positions, seq_len, n_windows=64):
    if seq_len <= 0:
        return []
    counts, edges = np.histogram(positions, bins=n_windows, range=(0, seq_len))
    width_mb = (seq_len / n_windows) / 1_000_000.0
    centers_mb = ((edges[:-1] + edges[1:]) * 0.5) / 1_000_000.0
    density = counts / max(width_mb, 1e-12)
    return [[sig(x, 5), sig(y, 5)] for x, y in zip(centers_mb, density)]


def map_preview(positions, rates, max_points=64):
    positions = np.asarray(positions, dtype=float)
    rates = np.asarray(rates, dtype=float)
    if positions.size == 0 or rates.size == 0:
        return []
    x = positions[:-1] if positions.size == rates.size + 1 else positions[: rates.size]
    y = rates[: x.size]
    valid = np.isfinite(x) & np.isfinite(y) & (y > 0)
    x = x[valid]
    y = y[valid]
    if x.size == 0:
        return []
    if x.size > max_points:
        idx = np.unique(np.linspace(0, x.size - 1, max_points).round().astype(int))
        x = x[idx]
        y = y[idx]
    return [[sig(pos / 1_000_000.0, 5), sig(rate, 5)] for pos, rate in zip(x, y)]


def count_distribution(samples, field):
    counts = Counter(str(sample.get(field, "NA")) for sample in samples)
    return [{"value": key, "count": value} for key, value in counts.most_common()]


def numeric_ranges(samples):
    result = {}
    for field in [
        "n_variants",
        "variant_density_per_mb",
        "Ne_ratio_max_min",
        "missing_rate",
        "genotype_error",
        "phase_switch_pair_count",
    ]:
        values = [sample[field] for sample in samples if isinstance(sample.get(field), (int, float))]
        if values:
            result[field] = {"min": min(values), "max": max(values)}
    return result


def manifest_value(manifest, key, default=None):
    if key in manifest:
        return manifest[key]
    samples = manifest.get("samples")
    if isinstance(samples, dict) and key in samples:
        return samples[key]
    return default


def manifest_storage_human(manifest):
    storage = manifest.get("storage")
    if isinstance(storage, dict) and storage.get("sample_files_human"):
        return storage["sample_files_human"]
    samples = manifest.get("samples")
    if isinstance(samples, dict):
        storage = samples.get("storage")
        if isinstance(storage, dict) and storage.get("sample_files_human"):
            return storage["sample_files_human"]
        if samples.get("samples_gb") is not None:
            return f"{float(samples['samples_gb']):.2f} GB"
    return ""


def hf_sample_path(path):
    value = str(path or "").replace("\\", "/")
    return value.removeprefix("samples/")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", default="/Users/larryivanhan/Desktop/DLCoalSim-10Mb-v1")
    parser.add_argument("--out", default="public/data")
    parser.add_argument("--dataset-id", default="DLCoalSim-10Mb-v1")
    parser.add_argument("--hf-repo", default="Larrivhan/DLCoalSim-10Mb-v1")
    parser.add_argument("--detail-out", default=None, help="write heavy detail chunks here instead of under --out")
    parser.add_argument("--detail-url-base", default=None, help="absolute URL prefix for detail chunks")
    parser.add_argument("--detail-chunk-size", type=int, default=512)
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    out_dir = Path(args.out)
    dataset_out = out_dir / args.dataset_id
    dataset_out.mkdir(parents=True, exist_ok=True)
    detail_root = Path(args.detail_out) if args.detail_out else dataset_out
    details_dir = detail_root / "details"
    details_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((dataset_dir / "manifest.json").read_text())
    rows = read_metadata(dataset_dir / "metadata" / "samples.csv")
    add_targets(rows, dataset_dir / "samples")

    hf_base = f"https://huggingface.co/datasets/{args.hf_repo}/resolve/main"
    detail_samples = []
    for sample in rows.values():
        sample.setdefault("target_log10_ne", [])
        shard_file = hf_sample_path(sample["shard_file"])
        shard_meta = hf_sample_path(sample["shard_metadata_file"])
        sample["hf_shard_url"] = f"{hf_base}/samples/{shard_file}"
        sample["hf_metadata_url"] = f"{hf_base}/samples/{shard_meta}"
        detail_samples.append(sample)
    detail_samples.sort(key=lambda item: item["sample_id"])

    index_samples = []
    detail_url_base = args.detail_url_base.rstrip("/") if args.detail_url_base else ""
    for chunk_id, start in enumerate(range(0, len(detail_samples), args.detail_chunk_size)):
        chunk = detail_samples[start : start + args.detail_chunk_size]
        detail_file = f"details/detail_{chunk_id:05d}.json"
        (detail_root / detail_file).write_text(json.dumps(chunk, separators=(",", ":")) + "\n")
        for detail_index, sample in enumerate(chunk):
            index_row = {field: sample[field] for field in INDEX_FIELDS}
            index_row["detail_file"] = detail_file
            index_row["detail_index"] = detail_index
            index_samples.append(index_row)

    distributions = {field: count_distribution(detail_samples, field) for field in COUNT_FIELDS}
    dataset_detail = {
        "id": args.dataset_id,
        "manifest": manifest,
        "distributions": distributions,
        "numeric_ranges": numeric_ranges(detail_samples),
    }
    registry = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "datasets": [
            {
                "id": args.dataset_id,
                "name": args.dataset_id,
                "n_samples": manifest_value(manifest, "n_samples", len(detail_samples)),
                "n_shards": manifest_value(manifest, "n_shards", 0),
                "sequence_length_bp": manifest_value(manifest, "sequence_length_bp", 0),
                "n_haplotypes": manifest_value(manifest, "n_haplotypes", 0),
                "time_bins": manifest_value(manifest, "time_bins", 0),
                "sample_files_human": manifest_storage_human(manifest),
                "hf_repo": args.hf_repo,
                "hf_url": f"https://huggingface.co/datasets/{args.hf_repo}",
                "detail_base_url": detail_url_base or "",
                "index_path": f"data/{args.dataset_id}/samples.json",
                "detail_path": f"data/{args.dataset_id}/dataset.json",
            }
        ],
    }

    (out_dir / "registry.json").write_text(json.dumps(registry, separators=(",", ":")) + "\n")
    (dataset_out / "dataset.json").write_text(json.dumps(dataset_detail, separators=(",", ":")) + "\n")
    (dataset_out / "samples.json").write_text(json.dumps(index_samples, separators=(",", ":")) + "\n")
    print(f"wrote {len(index_samples)} sample index rows to {dataset_out / 'samples.json'}")
    print(f"wrote {len(list(details_dir.glob('detail_*.json')))} detail chunks to {details_dir}")


if __name__ == "__main__":
    main()
