#!/usr/bin/env python3
"""
Benchmark the indexing pipeline to estimate processing time.

This script prepares sample datasets of configurable sizes, runs the full
pipeline (registration + hashing, embedding generation, FAISS indexing,
duplicate detection), and reports per-stage timing plus extrapolated
estimates for very large collections (e.g., 4 million images).
"""

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Sequence

from src.config import Config
from src.pipeline import IndexingPipeline
from src.faiss_index import FAISSIndex


def human_time(seconds: float) -> str:
    """Return a human-friendly time string."""
    if seconds < 1:
        return f"{seconds * 1000:.1f} ms"
    if seconds < 60:
        return f"{seconds:.2f} s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {secs:.1f}s"
    hours, mins = divmod(minutes, 60)
    return f"{int(hours)}h {int(mins)}m {secs:.0f}s"


def gather_images(image_dir: Path, extensions: Sequence[str]) -> List[Path]:
    """Collect all candidate image files from a directory."""
    exts = {ext.lower() for ext in extensions}
    files: List[Path] = []
    for path in image_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in exts:
            files.append(path)
    return sorted(files)


def prepare_sample(images: Iterable[Path], target_dir: Path, count: int) -> List[Path]:
    """Populate target_dir with symlinks (or copies) for the first `count` images."""
    selected = []
    target_dir.mkdir(parents=True, exist_ok=True)

    for idx, src in enumerate(images):
        if idx >= count:
            break
        dest_name = f"{idx:06d}_{src.name}"
        dest = target_dir / dest_name

        if dest.exists():
            dest.unlink()

        try:
            symlink_target = src.resolve()
            os.symlink(symlink_target, dest)
        except OSError:
            shutil.copy2(src, dest)

        selected.append(dest)

    return selected


def build_faiss_index(config: Config, embeddings_count: int) -> None:
    """Build a FAISS index using the embeddings saved by the pipeline."""
    embeddings = config.embeddings_path
    if not embeddings.exists():
        raise FileNotFoundError(f"Embeddings not found at {embeddings}")

    import numpy as np

    matrix = np.load(embeddings)
    index = FAISSIndex(config.embedding_dim, config.index_path)

    use_gpu = config.device == "cuda"
    if embeddings_count < config.nlist:
        index.build_flat_index(matrix, use_gpu=use_gpu)
    else:
        index.build_ivf_pq_index(
            matrix,
            nlist=config.nlist,
            m=config.m_pq,
            nbits=config.nbits_pq,
            use_gpu=use_gpu,
        )
    index.save()


@dataclass
class BenchmarkResult:
    images: int
    scan_seconds: float
    embed_seconds: float
    index_seconds: float
    duplicate_seconds: float

    @property
    def total_seconds(self) -> float:
        return (
            self.scan_seconds
            + self.embed_seconds
            + self.index_seconds
            + self.duplicate_seconds
        )

    def per_image_seconds(self) -> float:
        return self.total_seconds / self.images if self.images else 0.0


def benchmark_sample(
    sample_size: int,
    source_images: List[Path],
    output_root: Path,
    base_config: Config,
) -> BenchmarkResult:
    """Run the pipeline for a sample size and capture timings."""
    sample_root = output_root / f"sample_{sample_size}"
    images_dir = sample_root / "images"
    data_dir = sample_root / "data"

    if sample_root.exists():
        shutil.rmtree(sample_root)

    selected = prepare_sample(source_images, images_dir, sample_size)
    if len(selected) < sample_size:
        raise ValueError(
            f"Requested {sample_size} images but only found {len(selected)} in source directory."
        )

    config = Config(
        data_dir=data_dir,
        db_path=data_dir / "metadata.db",
        index_path=data_dir / "faiss.index",
        embeddings_path=data_dir / "embeddings.npy",
        thumbnails_dir=data_dir / "thumbnails",
        model_name=base_config.model_name,
        pretrained=base_config.pretrained,
        device=base_config.device,
        batch_size=base_config.batch_size,
        embedding_dim=base_config.embedding_dim,
        nlist=base_config.nlist,
        m_pq=base_config.m_pq,
        nbits_pq=base_config.nbits_pq,
        nprobe=base_config.nprobe,
        top_k_ivf=base_config.top_k_ivf,
        top_k_refined=base_config.top_k_refined,
        num_workers=base_config.num_workers,
        checkpoint_interval=base_config.checkpoint_interval,
        duplicate_hash_threshold=base_config.duplicate_hash_threshold,
    )

    pipeline = IndexingPipeline(config)

    timings = {}

    start = time.perf_counter()
    registered = pipeline.scan_and_register_images(images_dir)
    timings["scan"] = time.perf_counter() - start

    start = time.perf_counter()
    embedded = pipeline.generate_embeddings(resume=False)
    timings["embed"] = time.perf_counter() - start

    start = time.perf_counter()
    build_faiss_index(config, embedded)
    timings["index"] = time.perf_counter() - start

    start = time.perf_counter()
    duplicates = pipeline.db.mark_duplicates(
        hash_threshold=config.duplicate_hash_threshold
    )
    timings["duplicates"] = time.perf_counter() - start

    pipeline.close()

    print(
        f"[sample {sample_size}] registered={registered}, "
        f"embedded={embedded}, duplicates={duplicates}"
    )

    return BenchmarkResult(
        images=embedded,
        scan_seconds=timings["scan"],
        embed_seconds=timings["embed"],
        index_seconds=timings["index"],
        duplicate_seconds=timings["duplicates"],
    )


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark the indexing pipeline.")
    parser.add_argument(
        "image_dir",
        type=Path,
        help="Directory containing source images to sample from.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        nargs="+",
        default=[10, 100, 1000],
        help="Sample sizes to benchmark (default: 10 100 1000).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmark_runs"),
        help="Directory to store benchmark artifacts.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional YAML config override to mirror production settings.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON results in addition to the summary table.",
    )
    return parser.parse_args(argv)


def load_base_config(config_path: Path | None) -> Config:
    if config_path:
        from src.config import load_config

        return load_config(config_path)
    return Config()


def print_summary(results: List[BenchmarkResult]) -> None:
    print("\nBenchmark Summary")
    print("=" * 72)
    header = f"{'Images':>8} | {'Scan':>10} | {'Embed':>10} | {'Index':>10} | {'Duplicates':>12} | {'Total':>10} | {'Per Image':>10}"
    print(header)
    print("-" * len(header))

    for result in results:
        print(
            f"{result.images:8d} | "
            f"{human_time(result.scan_seconds):>10} | "
            f"{human_time(result.embed_seconds):>10} | "
            f"{human_time(result.index_seconds):>10} | "
            f"{human_time(result.duplicate_seconds):>12} | "
            f"{human_time(result.total_seconds):>10} | "
            f"{result.per_image_seconds():>10.4f}s"
        )

    largest = max(results, key=lambda r: r.images)
    per_image = largest.per_image_seconds()
    estimate_seconds = per_image * 4_000_000
    print("\nEstimated Time for 4,000,000 images (linear extrapolation)")
    print("-" * 72)
    print(
        f"Per-image (from {largest.images} sample): {per_image:.4f}s "
        f"→ total ≈ {human_time(estimate_seconds)}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if not args.image_dir.exists():
        print(f"Error: image_dir '{args.image_dir}' does not exist.", file=sys.stderr)
        return 1

    args.samples = sorted(set(args.samples))

    base_config = load_base_config(args.config)
    source_images = gather_images(args.image_dir, base_config.image_extensions)

    if not source_images:
        print("Error: no images found in the provided directory.", file=sys.stderr)
        return 1

    if max(args.samples) > len(source_images):
        print(
            f"Warning: not enough images in source directory ({len(source_images)} available).",
            file=sys.stderr,
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    results: List[BenchmarkResult] = []

    for sample in args.samples:
        if sample > len(source_images):
            print(f"Skipping sample size {sample} (insufficient images).")
            continue
        print(f"\n=== Benchmarking {sample} images ===")
        result = benchmark_sample(
            sample_size=sample,
            source_images=source_images,
            output_root=args.output_dir,
            base_config=base_config,
        )
        results.append(result)

    if not results:
        print("No benchmarks were executed.", file=sys.stderr)
        return 1

    print_summary(results)

    if args.json:
        print("\nJSON Results")
        print(json.dumps([asdict(r) for r in results], indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

