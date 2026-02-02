# Settlement Gallery - Vercel Deploy

Single-page gallery for reviewing and rating settlement images.

## Live URL
https://village-gallery.vercel.app

## Features

- **5,331 verified settlement images** from semantic search
- **Sorted by semantic similarity** to "settlement" query (highest first)
- **Selection**: Left-click to select, right-click for modal
- **Bulk actions**: Rate or hide multiple selected images
- **Rating**: 1-5 stars, reset, or hide (-1)
- **Comments**: Add notes to individual images
- **Find Duplicates**: Auto-hide duplicate filenames (keeps highest score)
- **Find Similar**: Find images with similar semantic scores
- **Filters**: All visible, by rating, hidden only, unrated
- **Page jump**: Dropdown to jump to any page

## Supabase Backend

- **Project**: `vlmtxakutftzftccizjf`
- **Table**: `settlement_images`
- **Storage**: `settlement-images` bucket, `verified/` folder

### Table Schema
```sql
id UUID PRIMARY KEY
hex_id TEXT (MD5 hash of original_path, first 8 chars)
filename TEXT
original_path TEXT
storage_path TEXT
rating INTEGER (-1=hidden, 1-5=stars, NULL=unrated)
semantic_score REAL (similarity to "settlement" query)
comment TEXT
```

## Deploy

```bash
cd /Users/aviz/images-finder/gallery/vercel-deploy
vercel --prod --yes
```

## Related Scripts

- `upload_all_verified.py` - Upload thumbnails and insert records
- `mark_verified.py` - Mark verified images by filename match
- `gallery.db` - Local SQLite with verified images
