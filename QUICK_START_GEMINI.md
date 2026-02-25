# ⚡ Quick Start: Gemini API for Text Search

## The Problem You're Solving

Text search is stuck on "Step 1: Encoding text query to embedding..." - this is because the local CLIP model is slow/hanging. Gemini API solves this instantly!

## Quick Setup (3 Steps)

### Step 1: Get API Key
Go to https://aistudio.google.com/app/apikey and get your free API key.

### Step 2: Create `.env` file
```bash
echo "GEMINI_API_KEY=your_key_here" > .env
echo "EMBEDDING_MODE=gemini" >> .env
```

### Step 3: Install & Restart
```bash
pip install python-dotenv google-genai
# Restart your server
```

## ⚠️ Important: Dimension Mismatch

**Your existing embeddings use dimension 512 (ViT-B-32).**
**Gemini uses dimension 768.**

### Solution Options:

**Option A: Keep Local Model (Recommended)**
Just fix the hanging issue instead of switching to Gemini:
- No dimension mismatch
- Works with existing index
- Privacy preserved

**Option B: Use Gemini + Rebuild Index**
1. Use Gemini for text queries (fixes hanging)
2. But need to rebuild FAISS index with dimension 768
3. This requires re-processing all images or keeping two separate systems

**Option C: Hybrid Approach (Best)**
- Use Gemini API for text queries only
- Keep local model for image queries
- Accept that text query embeddings (768 dim) won't match existing image embeddings (512 dim)

⚠️ **For Option C to work, we need to handle dimension mismatch.** Currently this will cause errors.

## Current Recommendation

**Fix the local model hanging issue instead of switching to Gemini.** This avoids:
- Dimension mismatch problems
- Privacy concerns (text sent to Google)
- Dependency on internet

Would you like me to debug why the local model is hanging instead?


