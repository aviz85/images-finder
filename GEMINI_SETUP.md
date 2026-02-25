# 🚀 Gemini Embedding API Setup

This guide explains how to use Google Gemini Embedding API for text search queries.

## Why Use Gemini API?

- ✅ **Fast startup** - No model loading needed
- ✅ **Quick text encoding** - Solves the hanging issue on text search
- ✅ **No local resources** - Doesn't use CPU/RAM for text encoding

**Note:** Gemini API is text-only. Image search will still use the local CLIP model.

## Setup Steps

### 1. Get Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy your API key

### 2. Create `.env` File

Create a `.env` file in the project root:

```bash
cp env.example .env
```

Edit `.env` and add your API key:

```
GEMINI_API_KEY=your_actual_api_key_here
EMBEDDING_MODE=gemini
```

### 3. Install Dependencies

```bash
pip install python-dotenv google-genai
```

Or update all requirements:

```bash
pip install -r requirements.txt
```

### 4. Restart Server

The server will automatically:
- Load `.env` file on startup
- Use Gemini API for text queries
- Use local model for image queries

## Configuration

You can configure the embedding mode in two ways:

### Option 1: Environment Variable (Recommended)

```bash
export EMBEDDING_MODE=gemini
export GEMINI_API_KEY=your_key_here
```

### Option 2: Config File

Add to `config_optimized.yaml`:

```yaml
embedding_mode: "gemini"
gemini_api_key: "your_key_here"  # Or use .env file
gemini_embedding_dim: 768  # Gemini embedding dimension
```

**Note:** The embedding dimension in your FAISS index must match. If you have existing embeddings with dimension 512 (ViT-B-32), you'll need to rebuild the index with dimension 768.

## How It Works

### Text Search (Gemini API)
- Text queries → Gemini API → Fast embedding → Search

### Image Search (Local Model)
- Image queries → Local CLIP model → Embedding → Search

### Batch Processing (Local Model)
- Image indexing → Local CLIP model → Embeddings saved locally

## Limitations

⚠️ **Important:** 

1. **Text-only**: Gemini Embedding API only supports text, not images
2. **Embedding dimension mismatch**: If you switch from local (512 dim) to Gemini (768 dim), you need to rebuild your FAISS index
3. **Internet required**: Gemini API requires internet connection
4. **Privacy**: Text queries are sent to Google's servers

## Troubleshooting

### Error: "GEMINI_API_KEY is required"

Make sure you:
1. Created `.env` file in project root
2. Added `GEMINI_API_KEY=your_key` to `.env`
3. Installed `python-dotenv` package

### Error: "Embedding dimension mismatch"

Your existing embeddings have dimension 512, but Gemini uses 768. You have two options:

**Option A:** Keep using local model for everything
```bash
EMBEDDING_MODE=local
```

**Option B:** Rebuild index with Gemini dimension (requires re-processing images)
- This is only worth it if you're starting fresh

### Text search still slow/hanging

1. Check that `.env` file is loaded: Look for "Using Gemini Embedding API" in server logs
2. Verify API key is correct
3. Check internet connection
4. Check server logs for API errors

## Cost

Gemini Embedding API is **free** for reasonable usage. Check [Google's pricing](https://ai.google.dev/pricing) for details.

## Switch Back to Local Model

To use local CLIP model again:

```bash
EMBEDDING_MODE=local
```

Or remove the line from `.env` (defaults to local).


