# Image Explorer Web UI Guide

## Overview

The Image Explorer provides a modern, feature-rich web interface for browsing, searching, and rating your indexed images. Built with vanilla HTML, CSS, and JavaScript for maximum performance and simplicity.

---

## Features

### 🖼️ **Image Browsing**
- Grid-based layout with responsive design
- Thumbnail previews with lazy loading
- Pagination support (12, 24, 48, or 96 images per page)
- Real-time image count display

### 🔍 **Semantic Search**
- Natural language text search powered by CLIP
- Real-time search with debouncing
- Relevance score display for search results
- Support for complex queries

### ⭐ **Rating System**
- 5-star rating scale
- Optional comments for each rating
- Quick rating from grid view
- Detailed rating in modal view
- Rating statistics dashboard

### 🎛️ **Filtering & Sorting**
- Sort by: Date, Rating, Name, Size, Dimensions
- Filter by minimum rating
- Ascending/Descending order
- Combined filters support

### 📱 **Responsive Design**
- Mobile-friendly interface
- Adaptive grid layout
- Touch-optimized controls
- Works on all screen sizes

---

## Getting Started

### 1. Start the Server

```bash
python server.py
```

The server will start on `http://localhost:8000`

### 2. Access the UI

Open your browser and navigate to:
```
http://localhost:8000/ui
```

Or use the root URL which will redirect to the UI:
```
http://localhost:8000
```

---

## User Interface Guide

### Main Screen

```
┌─────────────────────────────────────────────────────────┐
│  🖼️ Image Explorer     [Search Box]       📊 Stats      │
├─────────────────────────────────────────────────────────┤
│  Sort: [Date ▼] [DESC ▼]  Rating: [Any ▼]  [Refresh]  │
├─────────────────────────────────────────────────────────┤
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐     │
│  │ IMG │ │ IMG │ │ IMG │ │ IMG │ │ IMG │ │ IMG │     │
│  │ ⭐⭐⭐ │ │ ⭐⭐  │ │ ⭐⭐⭐⭐│ │     │ │ ⭐⭐⭐⭐⭐│ │ ⭐   │     │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘     │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐     │
│  │ IMG │ │ IMG │ │ IMG │ │ IMG │ │ IMG │ │ IMG │     │
│  │ ⭐⭐  │ │ ⭐⭐⭐ │ │ ⭐⭐⭐⭐│ │ ⭐   │ │ ⭐⭐⭐ │ │ ⭐⭐⭐⭐│     │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘     │
├─────────────────────────────────────────────────────────┤
│         ‹ 1 2 3 ... 10 11 12 ... 99 100 ›              │
└─────────────────────────────────────────────────────────┘
```

### Components

#### Header
- **Logo & Title**: Application branding
- **Search Box**: Enter natural language queries
- **Stats**: Total images and average rating

#### Controls Bar
- **Sort By**: Choose sorting field
- **Order**: Ascending or descending
- **Min Rating**: Filter by minimum stars
- **Per Page**: Images per page (12/24/48/96)
- **Refresh Button**: Reload current view

#### Image Grid
- **Thumbnails**: Click any image to view details
- **File Name**: Displayed below thumbnail
- **Dimensions**: Image size in pixels
- **Star Rating**: Visual rating display

#### Pagination
- **Previous/Next**: Navigate pages
- **Page Numbers**: Direct page access
- **Ellipsis**: Indicates hidden pages

---

## How to Use

### Browse Images

1. **View All Images**
   - Navigate to `/ui`
   - Images load automatically
   - Scroll through the grid

2. **Change View Settings**
   - Select items per page (12, 24, 48, 96)
   - Choose sort criteria
   - Apply rating filters

3. **Navigate Pages**
   - Click page numbers
   - Use Previous/Next arrows
   - Direct jump to specific pages

### Search Images

1. **Text Search**
   - Click the search box
   - Type your query (e.g., "sunset over mountains")
   - Results appear automatically
   - Clear search to return to browse mode

2. **Search Tips**
   ```
   ✓ "cat sitting on couch" - Natural language
   ✓ "person wearing red shirt" - Descriptive
   ✓ "beach sunset" - Multiple keywords
   ✓ "dog playing frisbee" - Actions and objects
   ```

### Rate Images

#### Quick Rating (Grid View)
- Star icons show current rating
- Visual feedback only (click to open modal for rating)

#### Detailed Rating (Modal View)
1. Click any image in the grid
2. Modal opens with image details
3. Click stars to select rating (1-5)
4. Add optional comment
5. Click "Save Rating"

#### Delete Rating
1. Open image modal
2. Click "Delete Rating" button
3. Confirm deletion

### Filter & Sort

#### Filtering
```javascript
// Filter 4+ star images
Min Rating: 4 Stars

// Show all images
Min Rating: Any
```

#### Sorting Options
- **Date Added**: Newest or oldest first
- **Rating**: Highest or lowest rated
- **Name**: Alphabetical order
- **File Size**: Largest or smallest
- **Width/Height**: By dimensions

### View Image Details

Click any image to see:
- Full-size preview
- File name and path
- File size (formatted)
- Dimensions (width × height)
- Image format (JPEG, PNG, etc.)
- Current rating and comment
- Rating controls

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Esc` | Close modal |
| `/` | Focus search box |
| `←` | Previous page |
| `→` | Next page |

*(Some shortcuts may require browser support)*

---

## API Endpoints Used

The UI interacts with these endpoints:

### Browse & Pagination
```
GET /browse?page=1&per_page=24&sort_by=created_at&sort_order=DESC
```

### Search
```
GET /search/text?q=sunset&top_k=48
```

### Ratings
```
GET    /rating/{image_id}        # Get rating
POST   /rating/{image_id}        # Set rating
DELETE /rating/{image_id}        # Delete rating
GET    /rating-stats             # Get statistics
```

### Images
```
GET /thumbnail/{image_id}        # Get thumbnail
GET /image/{image_id}            # Get image info
```

### Statistics
```
GET /stats                       # System stats
```

---

## Configuration

### Customizing the UI

Edit `static/index.html` to modify:
- Colors (CSS variables in `:root`)
- Grid layout (`.image-grid`)
- Items per page options
- Sort fields

### CSS Variables

```css
:root {
    --primary: #3b82f6;          /* Primary color */
    --star-color: #fbbf24;       /* Star color */
    --background: #f8fafc;       /* Page background */
    --card-bg: #ffffff;          /* Card background */
}
```

### JavaScript Configuration

Edit `static/app.js` to modify:
- Search debounce delay (currently 500ms)
- Default items per page
- Maximum page buttons shown
- Rating behavior

---

## Troubleshooting

### Images Not Loading
1. Ensure server is running (`python server.py`)
2. Check that images are indexed (`python cli.py stats`)
3. Verify database contains images
4. Check browser console for errors

### Search Not Working
1. Confirm FAISS index is built (`python cli.py build-index`)
2. Verify embeddings exist
3. Check search engine initialized (see server logs)
4. Try clearing search and browsing

### Ratings Not Saving
1. Check browser console for errors
2. Verify database permissions
3. Ensure valid image ID
4. Check network tab for failed requests

### Performance Issues
1. Reduce items per page
2. Use pagination instead of loading all
3. Check browser performance tools
4. Optimize thumbnail size

---

## Advanced Usage

### Custom Sorting

Add new sort fields in `src/database.py`:
```python
allowed_sorts = ['created_at', 'rating', 'file_name', 'custom_field']
```

Then update UI select options.

### Bulk Operations

Extend the UI with:
- Batch rating
- Multi-select
- Bulk export
- Collections/Albums

### Integration

The UI can be:
- Embedded in other applications
- Extended with React/Vue/Angular
- Customized with CSS frameworks
- Integrated with external systems

---

## Best Practices

### Organization
- Rate images consistently
- Use descriptive comments
- Create a rating system that works for you

### Search
- Use natural language
- Be descriptive but concise
- Combine multiple concepts
- Try different phrasings

### Performance
- Index images in batches
- Build FAISS index after bulk imports
- Use appropriate page sizes
- Monitor memory usage for large collections

---

## Example Workflows

### Workflow 1: Finding Vacation Photos
```
1. Search: "beach vacation sunset"
2. Filter: Min Rating 4 stars
3. Sort: By rating (DESC)
4. Browse results
5. Rate favorite images 5 stars
```

### Workflow 2: Organizing Recent Photos
```
1. Sort: By date (DESC)
2. Browse new images
3. Rate each image
4. Add comments for context
5. Filter by rating to find best
```

### Workflow 3: Finding Specific Subject
```
1. Search: "person wearing glasses"
2. Review search results
3. Click images for details
4. Rate relevant images
5. Save queries for later
```

---

## Support

For issues or questions:
- Check server logs
- Review browser console
- Verify API endpoints with `/docs`
- Check database with CLI tools

---

## Future Enhancements

Potential additions:
- Bulk rating interface
- Collections/Albums
- Image editing/cropping
- Export/Share functionality
- Advanced filters
- Keyboard navigation
- Dark mode
- Custom themes

Enjoy exploring your images! 🎨🖼️
