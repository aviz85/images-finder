#!/usr/bin/env python3
"""Test script to verify installation."""

import sys

def test_imports():
    """Test that all required packages can be imported."""
    print("Testing imports...")

    packages = [
        ('torch', 'PyTorch'),
        ('PIL', 'Pillow'),
        ('open_clip', 'open-clip-torch'),
        ('faiss', 'faiss-cpu or faiss-gpu'),
        ('numpy', 'numpy'),
        ('click', 'click'),
        ('tqdm', 'tqdm'),
        ('fastapi', 'fastapi'),
        ('pydantic', 'pydantic'),
    ]

    failed = []
    for package, name in packages:
        try:
            __import__(package)
            print(f"  ✓ {name}")
        except ImportError:
            print(f"  ✗ {name} - NOT FOUND")
            failed.append(name)

    if failed:
        print(f"\nMissing packages: {', '.join(failed)}")
        print("Run: pip install -r requirements.txt")
        return False

    print("\nAll packages installed successfully!")
    return True


def test_cuda():
    """Test CUDA availability."""
    print("\nTesting CUDA...")
    import torch

    if torch.cuda.is_available():
        print(f"  ✓ CUDA available")
        print(f"  ✓ GPU: {torch.cuda.get_device_name(0)}")
        print(f"  ✓ CUDA version: {torch.version.cuda}")
    else:
        print("  ⚠ CUDA not available - will use CPU (slower)")

    return True


def test_faiss():
    """Test FAISS."""
    print("\nTesting FAISS...")
    import faiss
    import numpy as np

    # Create a simple index
    d = 128
    nb = 1000
    nq = 10

    np.random.seed(1234)
    xb = np.random.random((nb, d)).astype('float32')
    xq = np.random.random((nq, d)).astype('float32')

    index = faiss.IndexFlatL2(d)
    index.add(xb)
    D, I = index.search(xq, 5)

    print("  ✓ FAISS working correctly")

    # Check GPU support
    if faiss.get_num_gpus() > 0:
        print(f"  ✓ FAISS GPU support available ({faiss.get_num_gpus()} GPUs)")
    else:
        print("  ⚠ FAISS GPU support not available")

    return True


def test_openclip():
    """Test OpenCLIP model loading."""
    print("\nTesting OpenCLIP...")
    import open_clip
    import torch

    # Try loading a small model
    try:
        model, _, preprocess = open_clip.create_model_and_transforms(
            'ViT-B-32',
            pretrained='openai'
        )
        print("  ✓ OpenCLIP model loading works")

        # Get embedding dimension
        with torch.no_grad():
            dummy = torch.zeros(1, 3, 224, 224)
            output = model.encode_image(dummy)
            print(f"  ✓ Embedding dimension: {output.shape[1]}")

        return True
    except Exception as e:
        print(f"  ✗ Error loading model: {e}")
        return False


def test_project_structure():
    """Test that project files exist."""
    print("\nTesting project structure...")
    from pathlib import Path

    required_files = [
        'src/__init__.py',
        'src/config.py',
        'src/database.py',
        'src/embeddings.py',
        'src/faiss_index.py',
        'src/image_processor.py',
        'src/pipeline.py',
        'src/search.py',
        'cli.py',
        'server.py',
        'requirements.txt',
        'README.md',
    ]

    missing = []
    for file in required_files:
        if Path(file).exists():
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ {file} - MISSING")
            missing.append(file)

    if missing:
        print(f"\nMissing files: {', '.join(missing)}")
        return False

    print("\nAll project files present!")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Local Semantic Image Search - Installation Test")
    print("=" * 60)

    tests = [
        test_imports,
        test_project_structure,
        test_cuda,
        test_faiss,
        test_openclip,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n  ✗ Test failed with error: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    if all(results):
        print("✓ All tests passed! Installation is complete.")
        print("\nNext steps:")
        print("1. Run: python cli.py run-pipeline /path/to/images")
        print("2. Search: python cli.py search-text 'your query'")
        print("\nSee QUICKSTART.md for more information.")
    else:
        print("✗ Some tests failed. Please fix the issues above.")
        sys.exit(1)
    print("=" * 60)


if __name__ == '__main__':
    main()
