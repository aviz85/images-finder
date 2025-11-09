#!/usr/bin/env python3
"""Command-line interface for local semantic image search."""

import click
from pathlib import Path
import json

from src.config import Config, load_config
from src.pipeline import IndexingPipeline
from src.search import ImageSearchEngine
from src.faiss_index import FAISSIndex
from src.embeddings import EmbeddingCache


@click.group()
@click.option('--config', type=click.Path(exists=True), help='Path to config YAML file')
@click.pass_context
def cli(ctx, config):
    """Local semantic image search CLI."""
    ctx.ensure_object(dict)
    if config:
        ctx.obj['config'] = load_config(Path(config))
    else:
        ctx.obj['config'] = Config()


@cli.command()
@click.argument('image_dir', type=click.Path(exists=True))
@click.pass_context
def index(ctx, image_dir):
    """Scan and register images from a directory."""
    config = ctx.obj['config']
    pipeline = IndexingPipeline(config)

    click.echo(f"Scanning images in {image_dir}...")
    num_registered = pipeline.scan_and_register_images(Path(image_dir))
    click.echo(f"Registered {num_registered} new images")

    pipeline.close()


@cli.command()
@click.option('--resume/--no-resume', default=True, help='Resume from checkpoint')
@click.pass_context
def embed(ctx, resume):
    """Generate embeddings for all images."""
    config = ctx.obj['config']
    pipeline = IndexingPipeline(config)

    click.echo("Generating embeddings...")
    num_embedded = pipeline.generate_embeddings(resume=resume)
    click.echo(f"Generated {num_embedded} embeddings")

    pipeline.close()


@cli.command()
@click.option('--force', is_flag=True, help='Rebuild index even if it exists')
@click.pass_context
def build_index(ctx, force):
    """Build FAISS search index."""
    config = ctx.obj['config']

    if config.index_path.exists() and not force:
        click.echo(f"Index already exists at {config.index_path}")
        click.echo("Use --force to rebuild")
        return

    click.echo("Loading embeddings...")
    embedding_cache = EmbeddingCache(config.embeddings_path)
    embeddings = embedding_cache.load()

    faiss_index = FAISSIndex(config.embedding_dim, config.index_path)

    # Use flat index for small datasets (< 100 images)
    if len(embeddings) < 100:
        click.echo(f"Building flat index for {len(embeddings)} embeddings (small dataset)...")
        faiss_index.build_flat_index(
            embeddings,
            use_gpu=config.device == "cuda"
        )
    else:
        click.echo(f"Building FAISS IVF-PQ index for {len(embeddings)} embeddings...")
        faiss_index.build_ivf_pq_index(
            embeddings,
            nlist=config.nlist,
            m=config.m_pq,
            nbits=config.nbits_pq,
            use_gpu=config.device == "cuda"
        )

    click.echo("Saving index...")
    faiss_index.save()
    click.echo(f"Index saved to {config.index_path}")


@cli.command()
@click.argument('query', type=str)
@click.option('--top-k', default=20, help='Number of results to return')
@click.option('--json-output', is_flag=True, help='Output results as JSON')
@click.pass_context
def search_text(ctx, query, top_k, json_output):
    """Search for images using text query."""
    config = ctx.obj['config']
    engine = ImageSearchEngine(config, use_hybrid=True)
    engine.initialize()

    click.echo(f"Searching for: '{query}'")
    results = engine.search_by_text(query, top_k=top_k)

    if json_output:
        output = [r.to_dict() for r in results]
        click.echo(json.dumps(output, indent=2))
    else:
        click.echo(f"\nFound {len(results)} results:\n")
        for i, result in enumerate(results, 1):
            click.echo(f"{i}. {result.file_path}")
            click.echo(f"   Score: {result.score:.4f}")
            if result.width and result.height:
                click.echo(f"   Size: {result.width}x{result.height}")
            click.echo()

    engine.close()


@cli.command()
@click.argument('image_path', type=click.Path(exists=True))
@click.option('--top-k', default=20, help='Number of results to return')
@click.option('--json-output', is_flag=True, help='Output results as JSON')
@click.pass_context
def search_image(ctx, image_path, top_k, json_output):
    """Search for similar images using an image query."""
    config = ctx.obj['config']
    engine = ImageSearchEngine(config, use_hybrid=True)
    engine.initialize()

    click.echo(f"Searching for images similar to: {image_path}")
    results = engine.search_by_image(image_path, top_k=top_k)

    if json_output:
        output = [r.to_dict() for r in results]
        click.echo(json.dumps(output, indent=2))
    else:
        click.echo(f"\nFound {len(results)} results:\n")
        for i, result in enumerate(results, 1):
            click.echo(f"{i}. {result.file_path}")
            click.echo(f"   Score: {result.score:.4f}")
            if result.width and result.height:
                click.echo(f"   Size: {result.width}x{result.height}")
            click.echo()

    engine.close()


@cli.command()
@click.pass_context
def stats(ctx):
    """Show indexing statistics."""
    config = ctx.obj['config']
    pipeline = IndexingPipeline(config)

    stats = pipeline.get_stats()

    click.echo("Indexing Statistics:")
    click.echo(f"  Total images: {stats['total_images']}")
    click.echo(f"  Processed: {stats['processed_images']}")
    click.echo(f"  Unprocessed: {stats['unprocessed_images']}")
    click.echo(f"  Embedding cache size: {stats['embedding_cache_size']}")

    if config.index_path.exists():
        click.echo(f"  FAISS index: {config.index_path} (exists)")
    else:
        click.echo(f"  FAISS index: Not built")

    pipeline.close()


@cli.command()
@click.argument('image_dir', type=click.Path(exists=True))
@click.option('--resume/--no-resume', default=True, help='Resume from checkpoint')
@click.pass_context
def run_pipeline(ctx, image_dir, resume):
    """Run the complete indexing pipeline: scan -> embed -> build index."""
    config = ctx.obj['config']
    pipeline = IndexingPipeline(config)

    # Step 1: Scan and register
    click.echo("Step 1: Scanning and registering images...")
    num_registered = pipeline.scan_and_register_images(Path(image_dir))
    click.echo(f"Registered {num_registered} new images")

    # Step 2: Generate embeddings
    click.echo("\nStep 2: Generating embeddings...")
    num_embedded = pipeline.generate_embeddings(resume=resume)
    click.echo(f"Generated {num_embedded} embeddings")

    # Step 3: Build FAISS index
    click.echo("\nStep 3: Building FAISS index...")
    embeddings = pipeline.embedding_cache.load()
    faiss_index = FAISSIndex(config.embedding_dim, config.index_path)

    # Use flat index for small datasets (< 100 images)
    if len(embeddings) < 100:
        click.echo(f"Building flat index for {len(embeddings)} embeddings (small dataset)...")
        faiss_index.build_flat_index(
            embeddings,
            use_gpu=config.device == "cuda"
        )
    else:
        faiss_index.build_ivf_pq_index(
            embeddings,
            nlist=config.nlist,
            m=config.m_pq,
            nbits=config.nbits_pq,
            use_gpu=config.device == "cuda"
        )
    faiss_index.save()

    click.echo(f"\nPipeline complete! Ready to search {len(embeddings)} images.")
    pipeline.close()


if __name__ == '__main__':
    cli(obj={})
