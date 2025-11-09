// Global state
let currentPage = 1;
let currentImageId = null;
let searchTimeout = null;
let folderSearchTimeout = null;
let searchMode = 'browse';  // 'browse', 'text', or 'image'
let searchQuery = null;     // text string or image_id

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadImages();
    loadStats();
    loadTags();
    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    // Semantic Search
    document.getElementById('searchBox').addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            if (e.target.value.trim()) {
                searchImages(e.target.value);
            } else {
                loadImages();
            }
        }, 500);
    });

    // Folder Search
    document.getElementById('folderSearchBox').addEventListener('input', (e) => {
        clearTimeout(folderSearchTimeout);
        folderSearchTimeout = setTimeout(() => {
            currentPage = 1;
            loadImages();
        }, 500);
    });

    // Controls
    document.getElementById('sortBy').addEventListener('change', () => loadImages());
    document.getElementById('sortOrder').addEventListener('change', () => loadImages());
    document.getElementById('minRating').addEventListener('change', () => loadImages());
    document.getElementById('tagFilter').addEventListener('change', () => {
        currentPage = 1;
        loadImages();
    });
    document.getElementById('perPage').addEventListener('change', () => {
        currentPage = 1;
        loadImages();
    });
    document.getElementById('refreshBtn').addEventListener('click', () => {
        currentPage = 1;
        loadImages();
        loadStats();
        loadTags();
    });

    // Modal rating stars
    const stars = document.querySelectorAll('#modalRating .star');
    stars.forEach(star => {
        star.addEventListener('click', () => {
            const rating = parseInt(star.dataset.rating);
            setStarRating(rating);
        });
        star.addEventListener('mouseenter', () => {
            const rating = parseInt(star.dataset.rating);
            highlightStars(rating);
        });
    });

    document.getElementById('modalRating').addEventListener('mouseleave', () => {
        const currentRating = getCurrentStarRating();
        highlightStars(currentRating);
    });

    // Modal buttons
    document.getElementById('saveRatingBtn').addEventListener('click', saveRating);
    document.getElementById('deleteRatingBtn').addEventListener('click', deleteRating);
    document.getElementById('openInFinderBtn').addEventListener('click', () => {
        if (currentImageId) {
            openInExplorer(currentImageId);
        }
    });
    document.getElementById('findSimilarBtn').addEventListener('click', async () => {
        if (currentImageId) {
            // Save imageId before closing modal (closeModal sets currentImageId to null)
            const imageId = currentImageId;

            try {
                const response = await fetch(`/image/${imageId}`);
                const imageData = await response.json();

                // Close modal
                closeModal();

                // Start similarity search
                setTimeout(() => {
                    searchBySimilarImage(imageId, imageData.file_name);
                }, 100);
            } catch (error) {
                console.error('Error starting similarity search:', error);
            }
        }
    });

    // Close modal on background click
    document.getElementById('imageModal').addEventListener('click', (e) => {
        if (e.target.id === 'imageModal') {
            closeModal();
        }
    });
}

// Load images with pagination and filters
async function loadImages() {
    // If we're in image search mode, reload that search instead
    if (searchMode === 'image' && searchQuery) {
        try {
            const imgResponse = await fetch(`/image/${searchQuery}`);
            const imgData = await imgResponse.json();
            await searchBySimilarImage(searchQuery, imgData.file_name);
            return;
        } catch (error) {
            console.error('Error reloading image search:', error);
            // Fall through to normal browse
        }
    }

    // Reset search mode to browse
    searchMode = 'browse';
    searchQuery = null;

    // Reset search box placeholder
    const searchBox = document.getElementById('searchBox');
    searchBox.placeholder = 'Search images semantically...';

    const loading = document.getElementById('loading');
    const grid = document.getElementById('imageGrid');
    const pagination = document.getElementById('pagination');
    const emptyState = document.getElementById('emptyState');

    loading.style.display = 'block';
    grid.style.display = 'none';
    pagination.style.display = 'none';
    emptyState.style.display = 'none';

    try {
        const params = new URLSearchParams({
            page: currentPage,
            per_page: document.getElementById('perPage').value,
            sort_by: document.getElementById('sortBy').value,
            sort_order: document.getElementById('sortOrder').value
        });

        const minRating = document.getElementById('minRating').value;
        if (minRating) {
            params.append('min_rating', minRating);
        }

        // Get selected tag IDs from multiselect
        const tagFilter = document.getElementById('tagFilter');
        const selectedTags = Array.from(tagFilter.selectedOptions)
            .map(option => option.value)
            .filter(value => value !== ''); // Filter out empty "All tags" option
        if (selectedTags.length > 0) {
            params.append('tag_ids', selectedTags.join(','));
        }

        // Get folder search query
        const folderSearchBox = document.getElementById('folderSearchBox');
        const folderSearch = folderSearchBox.value.trim();
        if (folderSearch) {
            params.append('folder_path', folderSearch);
        }

        const response = await fetch(`/browse?${params}`);
        const data = await response.json();

        loading.style.display = 'none';

        if (data.images.length === 0) {
            emptyState.style.display = 'block';
        } else {
            displayImages(data.images);
            displayPagination(data);
            grid.style.display = 'grid';
            pagination.style.display = 'flex';
        }
    } catch (error) {
        console.error('Error loading images:', error);
        loading.style.display = 'none';
        emptyState.style.display = 'block';
    }
}

// Search images
async function searchImages(query) {
    // Update search mode
    searchMode = 'text';
    searchQuery = query;
    currentPage = 1;

    const loading = document.getElementById('loading');
    const grid = document.getElementById('imageGrid');
    const pagination = document.getElementById('pagination');
    const emptyState = document.getElementById('emptyState');

    loading.style.display = 'block';
    grid.style.display = 'none';
    pagination.style.display = 'none';
    emptyState.style.display = 'none';

    try {
        const response = await fetch(`/search/text?q=${encodeURIComponent(query)}&top_k=48`);
        const data = await response.json();

        loading.style.display = 'none';

        if (data.results.length === 0) {
            emptyState.style.display = 'block';
        } else {
            displaySearchResults(data.results);
            grid.style.display = 'grid';
        }
    } catch (error) {
        console.error('Error searching images:', error);
        loading.style.display = 'none';
        emptyState.style.display = 'block';
    }
}

// Search for images similar to a given image
async function searchBySimilarImage(imageId, imageName) {
    const loading = document.getElementById('loading');
    const grid = document.getElementById('imageGrid');
    const pagination = document.getElementById('pagination');
    const emptyState = document.getElementById('emptyState');
    const searchBox = document.getElementById('searchBox');

    // Update search state
    searchMode = 'image';
    searchQuery = imageId;
    currentPage = 1;

    // Clear text search box and show search indicator
    searchBox.value = '';
    searchBox.placeholder = `Searching for images similar to: ${imageName}`;

    loading.style.display = 'block';
    grid.style.display = 'none';
    pagination.style.display = 'none';
    emptyState.style.display = 'none';

    try {
        const params = new URLSearchParams({
            page: currentPage,
            per_page: document.getElementById('perPage').value
        });

        const response = await fetch(`/search/image/${imageId}?${params}`);
        const data = await response.json();

        loading.style.display = 'none';

        if (data.images.length === 0) {
            emptyState.style.display = 'block';
        } else {
            displaySearchResults(data.images);
            displayPagination(data);
            grid.style.display = 'grid';
            pagination.style.display = 'flex';
        }
    } catch (error) {
        console.error('Error searching similar images:', error);
        loading.style.display = 'none';
        emptyState.style.display = 'block';
    }
}

// Display images in grid
function displayImages(images) {
    const grid = document.getElementById('imageGrid');
    grid.innerHTML = '';

    images.forEach(image => {
        const card = createImageCard(image);
        grid.appendChild(card);
    });
}

// Display search results
function displaySearchResults(results) {
    const grid = document.getElementById('imageGrid');
    grid.innerHTML = '';

    results.forEach(result => {
        const card = createImageCard(result);

        // Add search score indicator if present
        const score = result.score || result.similarity_score;
        if (score !== undefined) {
            const scoreDiv = document.createElement('div');
            scoreDiv.style.cssText = 'position: absolute; top: 0.5rem; right: 0.5rem; background: rgba(0,0,0,0.7); color: white; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem;';
            scoreDiv.textContent = `${(score * 100).toFixed(0)}% match`;
            card.querySelector('.image-wrapper').appendChild(scoreDiv);
        }

        grid.appendChild(card);
    });
}

// Create image card element
function createImageCard(image) {
    const card = document.createElement('div');
    card.className = 'image-card';
    card.onclick = () => openImageModal(image);

    const rating = image.rating || 0;

    // Handle both 'id' (from browse) and 'image_id' (from search)
    const imageId = image.id || image.image_id;

    // Create folder chips HTML
    const folders = image.folders || [];
    const folderChipsHtml = folders.length > 0
        ? `<div class="folder-tags">${folders.map(f => `<span class="folder-chip" title="${f}">${f}</span>`).join('')}</div>`
        : '';

    // Create duplicate badge HTML
    const duplicateCount = image.duplicate_count || 0;
    const duplicateBadgeHtml = duplicateCount > 0
        ? `<div class="duplicate-badge" onclick="event.stopPropagation(); openDuplicatesModal(${imageId});">🔴 ${duplicateCount}</div>`
        : '';

    card.innerHTML = `
        <div class="image-wrapper">
            <img src="/thumbnail/${imageId}" alt="${image.file_name}" loading="lazy">
            ${duplicateBadgeHtml}
        </div>
        <div class="image-info">
            <div class="image-name" title="${image.file_name}">${image.file_name}</div>
            <div class="image-meta">
                <span>${image.width} × ${image.height}</span>
                <div class="rating-display">${createStarDisplay(rating)}</div>
            </div>
            ${folderChipsHtml}
        </div>
    `;

    const ratingDisplay = card.querySelector('.rating-display');
    initializeRatingControl(ratingDisplay, imageId, rating);

    return card;
}

// Create star display
function createStarDisplay(rating) {
    let html = '';
    for (let i = 1; i <= 5; i++) {
        const filled = i <= rating ? 'filled' : '';
        html += `<span class="star ${filled}" data-rating="${i}">★</span>`;
    }
    return html;
}

function initializeRatingControl(container, imageId, initialRating) {
    container.dataset.imageId = imageId;
    container.dataset.currentRating = initialRating || 0;
    container.dataset.updating = 'false';

    const stars = container.querySelectorAll('.star');
    stars.forEach(star => {
        const starValue = parseInt(star.dataset.rating, 10);

        star.addEventListener('click', (event) => {
            event.stopPropagation();
            submitInlineRating(container, imageId, starValue);
        });

        star.addEventListener('mouseenter', () => {
            updateInlineStarState(container, starValue);
        });

        star.addEventListener('mouseleave', () => {
            restoreInlineRating(container);
        });
    });

    container.addEventListener('mouseleave', () => {
        restoreInlineRating(container);
    });
}

function updateInlineStarState(container, rating) {
    const stars = container.querySelectorAll('.star');
    stars.forEach(star => {
        const starValue = parseInt(star.dataset.rating, 10);
        if (starValue <= rating) {
            star.classList.add('filled');
        } else {
            star.classList.remove('filled');
        }
    });
}

function restoreInlineRating(container) {
    const current = parseInt(container.dataset.currentRating, 10) || 0;
    updateInlineStarState(container, current);
}

async function submitInlineRating(container, imageId, rating) {
    if (container.dataset.updating === 'true') {
        return;
    }

    container.dataset.updating = 'true';
    updateInlineStarState(container, rating);

    try {
        const response = await fetch(`/rating/${imageId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rating, comment: null })
        });

        if (!response.ok) {
            throw new Error(`Rating request failed with status ${response.status}`);
        }

        container.dataset.currentRating = rating;
        showToast('Rating updated');
        loadStats();
    } catch (error) {
        console.error('Error updating rating:', error);
        showToast('Failed to update rating', 'error');
        restoreInlineRating(container);
    } finally {
        container.dataset.updating = 'false';
    }
}

// Display pagination
function displayPagination(data) {
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = '';

    const { page, total_pages } = data;

    // Previous button
    const prevBtn = document.createElement('button');
    prevBtn.textContent = '‹';
    prevBtn.disabled = page === 1;
    prevBtn.onclick = () => {
        if (page > 1) {
            currentPage = page - 1;
            loadImages();
        }
    };
    pagination.appendChild(prevBtn);

    // Page numbers
    const maxButtons = 7;
    let startPage = Math.max(1, page - Math.floor(maxButtons / 2));
    let endPage = Math.min(total_pages, startPage + maxButtons - 1);

    if (endPage - startPage < maxButtons - 1) {
        startPage = Math.max(1, endPage - maxButtons + 1);
    }

    if (startPage > 1) {
        const firstBtn = createPageButton(1);
        pagination.appendChild(firstBtn);
        if (startPage > 2) {
            const dots = document.createElement('span');
            dots.textContent = '...';
            dots.style.padding = '0 0.5rem';
            pagination.appendChild(dots);
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        const btn = createPageButton(i);
        if (i === page) btn.classList.add('active');
        pagination.appendChild(btn);
    }

    if (endPage < total_pages) {
        if (endPage < total_pages - 1) {
            const dots = document.createElement('span');
            dots.textContent = '...';
            dots.style.padding = '0 0.5rem';
            pagination.appendChild(dots);
        }
        const lastBtn = createPageButton(total_pages);
        pagination.appendChild(lastBtn);
    }

    // Next button
    const nextBtn = document.createElement('button');
    nextBtn.textContent = '›';
    nextBtn.disabled = page === total_pages;
    nextBtn.onclick = () => {
        if (page < total_pages) {
            currentPage = page + 1;
            loadImages();
        }
    };
    pagination.appendChild(nextBtn);
}

// Create page button
function createPageButton(pageNum) {
    const btn = document.createElement('button');
    btn.textContent = pageNum;
    btn.onclick = async () => {
        currentPage = pageNum;

        // Reload based on current search mode
        if (searchMode === 'image' && searchQuery) {
            try {
                const imgResponse = await fetch(`/image/${searchQuery}`);
                const imgData = await imgResponse.json();
                await searchBySimilarImage(searchQuery, imgData.file_name);
            } catch (error) {
                console.error('Error navigating image search:', error);
                loadImages();
            }
        } else if (searchMode === 'text' && searchQuery) {
            searchImages(searchQuery);
        } else {
            loadImages();
        }
    };
    return btn;
}

// Load statistics
async function loadStats() {
    try {
        const [statsRes, ratingStatsRes] = await Promise.all([
            fetch('/stats'),
            fetch('/rating-stats')
        ]);

        const stats = await statsRes.json();
        const ratingStats = await ratingStatsRes.json();

        document.getElementById('totalImages').textContent = stats.processed_images;

        if (ratingStats.avg_rating !== null) {
            document.getElementById('avgRating').textContent = ratingStats.avg_rating.toFixed(1);
        } else {
            document.getElementById('avgRating').textContent = '-';
        }
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Load tags for filter dropdown
async function loadTags() {
    try {
        const response = await fetch('/tags');
        const tags = await response.json();

        const tagFilter = document.getElementById('tagFilter');

        // Clear existing options except the "All tags" option
        tagFilter.innerHTML = '<option value="">All tags</option>';

        // Add tags as options
        tags.forEach(tag => {
            const option = document.createElement('option');
            option.value = tag.id;
            option.textContent = tag.name;
            tagFilter.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading tags:', error);
    }
}

// Open image modal
async function openImageModal(image) {
    // Handle both 'id' (from browse) and 'image_id' (from search)
    currentImageId = image.id || image.image_id;

    const modal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImage');
    const modalFileName = document.getElementById('modalFileName');
    const modalFileSize = document.getElementById('modalFileSize');
    const modalDimensions = document.getElementById('modalDimensions');
    const modalFormat = document.getElementById('modalFormat');
    const modalComment = document.getElementById('modalComment');

    // Set image details
    modalImage.src = `/thumbnail/${currentImageId}`;
    modalFileName.textContent = image.file_name;
    modalFileSize.textContent = formatFileSize(image.file_size);
    modalDimensions.textContent = `${image.width} × ${image.height}`;
    modalFormat.textContent = image.format;

    // Load existing rating
    try {
        const response = await fetch(`/rating/${currentImageId}`);
        const ratingData = await response.json();

        if (ratingData.rating) {
            setStarRating(ratingData.rating);
            modalComment.value = ratingData.comment || '';
        } else {
            setStarRating(0);
            modalComment.value = '';
        }
    } catch (error) {
        console.error('Error loading rating:', error);
        setStarRating(0);
        modalComment.value = '';
    }

    // Load tags
    loadImageTags(currentImageId);

    // Load similar images
    loadSimilarImages(currentImageId);

    modal.classList.add('show');
}

// Close modal
function closeModal() {
    document.getElementById('imageModal').classList.remove('show');
    currentImageId = null;
}

// Load similar images
async function loadSimilarImages(imageId) {
    const duplicatesContainer = document.getElementById('duplicatesContainer');
    const similarContainer = document.getElementById('similarImagesContainer');

    // Clear previous content
    duplicatesContainer.innerHTML = '';
    similarContainer.innerHTML = '';

    try {
        const response = await fetch(`/image/${imageId}/similar?limit=12`);
        const data = await response.json();

        // Display duplicates
        if (data.duplicates && data.duplicates.length > 0) {
            const heading = document.createElement('h4');
            heading.textContent = `Duplicates (${data.duplicates.length})`;
            duplicatesContainer.appendChild(heading);

            const grid = document.createElement('div');
            grid.className = 'similar-grid';

            data.duplicates.forEach(img => {
                const item = createSimilarImageItem(img);
                grid.appendChild(item);
            });

            duplicatesContainer.appendChild(grid);
        }

        // Display semantically similar images
        if (data.similar && data.similar.length > 0) {
            const heading = document.createElement('h4');
            heading.textContent = `Related Images (${data.similar.length})`;
            similarContainer.appendChild(heading);

            const grid = document.createElement('div');
            grid.className = 'similar-grid';

            data.similar.forEach(img => {
                const item = createSimilarImageItem(img);
                grid.appendChild(item);
            });

            similarContainer.appendChild(grid);
        }

        // Show message if no similar images at all
        if ((!data.duplicates || data.duplicates.length === 0) &&
            (!data.similar || data.similar.length === 0)) {
            const noSimilar = document.createElement('div');
            noSimilar.className = 'no-similar';
            noSimilar.textContent = 'No similar images found';
            duplicatesContainer.appendChild(noSimilar);
        }
    } catch (error) {
        console.error('Error loading similar images:', error);
        const errorMsg = document.createElement('div');
        errorMsg.className = 'no-similar';
        errorMsg.textContent = 'Failed to load similar images';
        duplicatesContainer.appendChild(errorMsg);
    }
}

// Create similar image item element
function createSimilarImageItem(image) {
    const item = document.createElement('div');
    item.className = 'similar-item';
    item.title = image.file_name;

    const img = document.createElement('img');
    img.src = `/thumbnail/${image.id}`;
    img.alt = image.file_name;
    img.loading = 'lazy';

    item.appendChild(img);

    // Click to open in modal
    item.onclick = () => {
        // Close current modal and open the clicked image
        closeModal();
        setTimeout(() => openImageModal(image), 100);
    };

    return item;
}

// Open image location in file explorer
async function openInExplorer(imageId) {
    try {
        const response = await fetch(`/open-in-explorer/${imageId}`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            showToast('Opened in file explorer');
        } else {
            showToast('Failed to open file explorer', 'error');
        }
    } catch (error) {
        console.error('Error opening in explorer:', error);
        showToast('Error opening file explorer', 'error');
    }
}

// Show toast notification
function showToast(message, type = 'success') {
    // Create toast element
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 2rem;
        right: 2rem;
        padding: 1rem 1.5rem;
        background: ${type === 'error' ? '#ef4444' : '#10b981'};
        color: white;
        border-radius: 0.5rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
    `;
    toast.textContent = message;

    document.body.appendChild(toast);

    // Remove after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Set star rating
function setStarRating(rating) {
    const stars = document.querySelectorAll('#modalRating .star');
    stars.forEach((star, index) => {
        if (index < rating) {
            star.classList.add('filled');
        } else {
            star.classList.remove('filled');
        }
    });
}

// Highlight stars on hover
function highlightStars(rating) {
    const stars = document.querySelectorAll('#modalRating .star');
    stars.forEach((star, index) => {
        if (index < rating) {
            star.classList.add('filled');
        } else {
            star.classList.remove('filled');
        }
    });
}

// Get current star rating
function getCurrentStarRating() {
    const stars = document.querySelectorAll('#modalRating .star');
    let rating = 0;
    stars.forEach((star, index) => {
        if (star.classList.contains('filled')) {
            rating = index + 1;
        }
    });
    return rating;
}

// Save rating
async function saveRating() {
    const rating = getCurrentStarRating();

    if (rating === 0) {
        alert('Please select a rating');
        return;
    }

    const comment = document.getElementById('modalComment').value;

    try {
        const response = await fetch(`/rating/${currentImageId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rating, comment })
        });

        if (response.ok) {
            closeModal();
            loadImages();
            loadStats();
        } else {
            alert('Error saving rating');
        }
    } catch (error) {
        console.error('Error saving rating:', error);
        alert('Error saving rating');
    }
}

// Delete rating
async function deleteRating() {
    if (!confirm('Are you sure you want to delete this rating?')) {
        return;
    }

    try {
        const response = await fetch(`/rating/${currentImageId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            closeModal();
            loadImages();
            loadStats();
        } else {
            alert('Error deleting rating');
        }
    } catch (error) {
        console.error('Error deleting rating:', error);
        alert('Error deleting rating');
    }
}

// Format file size
function formatFileSize(bytes) {
    if (!bytes) return '-';

    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;

    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }

    return `${size.toFixed(1)} ${units[unitIndex]}`;
}

// Open duplicates modal
async function openDuplicatesModal(imageId) {
    const modal = document.getElementById('duplicatesModal');
    const grid = document.getElementById('duplicatesGrid');
    const title = document.getElementById('duplicatesModalTitle');

    try {
        const response = await fetch(`/image/${imageId}/duplicates`);
        const data = await response.json();

        title.textContent = `Duplicate Images (${data.count})`;

        // Clear previous content
        grid.innerHTML = '';

        if (data.duplicates && data.duplicates.length > 0) {
            data.duplicates.forEach(dup => {
                const item = document.createElement('div');
                item.className = 'duplicate-item';

                item.innerHTML = `
                    <div class="duplicate-thumbnail">
                        <img src="/thumbnail/${dup.id}" alt="${dup.file_name}" loading="lazy">
                    </div>
                    <div class="duplicate-path" title="${dup.file_path}">${dup.file_path}</div>
                    <button class="explorer-btn" onclick="event.stopPropagation(); openInExplorer(${dup.id});" title="Open in Explorer">
                        🔍
                    </button>
                `;

                grid.appendChild(item);
            });
        } else {
            grid.innerHTML = '<p class="no-similar">No duplicates found</p>';
        }

        modal.classList.add('show');
    } catch (error) {
        console.error('Error loading duplicates:', error);
        grid.innerHTML = '<p class="no-similar">Error loading duplicates</p>';
        modal.classList.add('show');
    }
}

// Close duplicates modal
function closeDuplicatesModal() {
    document.getElementById('duplicatesModal').classList.remove('show');
}

// ==================== Tag Management ====================

let allTags = [];
let currentImageTags = [];

// Load all available tags
async function loadAllTags() {
    try {
        const response = await fetch('/tags');
        const data = await response.json();
        allTags = data.tags || [];
    } catch (error) {
        console.error('Error loading tags:', error);
        allTags = [];
    }
}

// Load tags for current image
async function loadImageTags(imageId) {
    const tagChips = document.getElementById('tagChips');

    try {
        const response = await fetch(`/image/${imageId}/tags`);
        const data = await response.json();
        currentImageTags = data.tags || [];

        displayTags();
    } catch (error) {
        console.error('Error loading image tags:', error);
        currentImageTags = [];
        tagChips.innerHTML = '<p class="no-tags">Error loading tags</p>';
    }
}

// Display current tags as chips
function displayTags() {
    const tagChips = document.getElementById('tagChips');

    if (currentImageTags.length === 0) {
        tagChips.innerHTML = '<p class="no-tags">No tags yet</p>';
        return;
    }

    tagChips.innerHTML = currentImageTags.map(tag => `
        <div class="tag-chip">
            <span>${tag.name}</span>
            <span class="tag-chip-remove" onclick="removeTag(${tag.id})">&times;</span>
        </div>
    `).join('');
}

// Remove tag from image
async function removeTag(tagId) {
    if (!currentImageId) return;

    try {
        await fetch(`/image/${currentImageId}/tags/${tagId}`, {
            method: 'DELETE'
        });

        // Reload tags
        await loadImageTags(currentImageId);
    } catch (error) {
        console.error('Error removing tag:', error);
        alert('Failed to remove tag');
    }
}

// Add tag to image
async function addTag(tagId) {
    if (!currentImageId) return;

    try {
        await fetch(`/image/${currentImageId}/tags`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tag_id: tagId })
        });

        // Reload tags
        await loadImageTags(currentImageId);
    } catch (error) {
        console.error('Error adding tag:', error);
        alert('Failed to add tag');
    }
}

// Create new tag
async function createTag(tagName) {
    try {
        const response = await fetch('/tags', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: tagName })
        });

        const data = await response.json();

        // Reload all tags
        await loadAllTags();

        return data.tag_id;
    } catch (error) {
        console.error('Error creating tag:', error);
        throw error;
    }
}

// Setup tag input and autocomplete
document.addEventListener('DOMContentLoaded', () => {
    const tagInput = document.getElementById('tagInput');
    const autocomplete = document.getElementById('tagAutocomplete');

    // Load all tags on page load
    loadAllTags();

    // Tag input handler
    tagInput.addEventListener('input', () => {
        const query = tagInput.value.trim().toLowerCase();

        if (query.length === 0) {
            autocomplete.classList.remove('show');
            return;
        }

        // Filter tags that match query and aren't already added
        const currentTagIds = new Set(currentImageTags.map(t => t.id));
        const matches = allTags.filter(tag =>
            tag.name.toLowerCase().includes(query) &&
            !currentTagIds.has(tag.id)
        );

        if (matches.length === 0) {
            // Show option to create new tag
            autocomplete.innerHTML = `
                <div class="tag-autocomplete-item" onclick="createAndAddTag('${query.replace(/'/g, "\\'")}')">
                    Create new tag: "${query}"
                </div>
            `;
            autocomplete.classList.add('show');
        } else {
            // Show matching tags
            autocomplete.innerHTML = matches.map(tag => `
                <div class="tag-autocomplete-item" onclick="selectTag(${tag.id})">
                    ${tag.name} ${tag.count > 0 ? `(${tag.count})` : ''}
                </div>
            `).join('');
            autocomplete.classList.add('show');
        }
    });

    // Enter key to create tag
    tagInput.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const tagName = tagInput.value.trim();
            if (tagName) {
                await createAndAddTag(tagName);
            }
        }
    });

    // Close autocomplete when clicking outside
    document.addEventListener('click', (e) => {
        if (!tagInput.contains(e.target) && !autocomplete.contains(e.target)) {
            autocomplete.classList.remove('show');
        }
    });
});

// Select tag from autocomplete
async function selectTag(tagId) {
    await addTag(tagId);

    const tagInput = document.getElementById('tagInput');
    const autocomplete = document.getElementById('tagAutocomplete');

    tagInput.value = '';
    autocomplete.classList.remove('show');
}

// Create and add new tag
async function createAndAddTag(tagName) {
    try {
        const tagId = await createTag(tagName);
        await addTag(tagId);

        const tagInput = document.getElementById('tagInput');
        const autocomplete = document.getElementById('tagAutocomplete');

        tagInput.value = '';
        autocomplete.classList.remove('show');

        // Reload tag filter to include the new tag
        loadTags();
    } catch (error) {
        alert('Failed to create tag');
    }
}

// ==================== Folder Indexing ====================

let indexingPollInterval = null;

// Open index modal
function openIndexModal() {
    document.getElementById('indexModal').classList.add('show');
    document.getElementById('folderPathInput').value = '';
    document.getElementById('indexProgress').style.display = 'none';
}

// Close index modal
function closeIndexModal() {
    document.getElementById('indexModal').classList.remove('show');
    if (indexingPollInterval) {
        clearInterval(indexingPollInterval);
        indexingPollInterval = null;
    }
}

// Start indexing
async function startIndexing() {
    const folderPath = document.getElementById('folderPathInput').value.trim();

    if (!folderPath) {
        alert('Please enter a folder path');
        return;
    }

    try {
        const response = await fetch('/index/folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_path: folderPath })
        });

        const data = await response.json();

        if (!data.success) {
            alert(data.message);
            return;
        }

        // Show progress UI
        document.getElementById('indexProgress').style.display = 'block';
        document.getElementById('startIndexBtn').disabled = true;

        // Start polling for progress
        pollIndexProgress();
        indexingPollInterval = setInterval(pollIndexProgress, 1000);

    } catch (error) {
        console.error('Error starting indexing:', error);
        alert('Failed to start indexing');
    }
}

// Poll for indexing progress
async function pollIndexProgress() {
    try {
        const response = await fetch('/index/progress');
        const progress = await response.json();

        // Update UI
        document.getElementById('indexPhase').textContent = progress.phase || 'Initializing';
        document.getElementById('indexMessage').textContent = progress.message || '';

        if (progress.total_images > 0) {
            const percent = (progress.processed_images / progress.total_images) * 100;
            document.getElementById('indexProgressBar').style.width = percent + '%';
            document.getElementById('indexStatus').textContent =
                `${progress.processed_images}/${progress.total_images}`;
        }

        // Check if complete
        if (progress.phase === 'complete' || progress.phase === 'error') {
            clearInterval(indexingPollInterval);
            indexingPollInterval = null;
            document.getElementById('startIndexBtn').disabled = false;

            if (progress.phase === 'complete') {
                document.getElementById('indexProgressBar').style.width = '100%';
                document.getElementById('indexProgressBar').style.background = 'var(--success)';

                // Reload stats and images
                setTimeout(() => {
                    loadStats();
                    loadImages();
                    closeIndexModal();
                }, 2000);
            } else {
                document.getElementById('indexProgressBar').style.background = '#ef4444';
            }
        }

    } catch (error) {
        console.error('Error polling progress:', error);
    }
}

// Browse for folder
function browseFolder() {
    document.getElementById('folderBrowser').click();
}

// Handle folder selection
function handleFolderSelection(event) {
    const files = event.target.files;
    if (files.length > 0) {
        const firstFile = files[0];
        let folderPath = '';

        // Try multiple methods to get the full path
        // Method 1: Direct path property (Electron, some desktop browsers)
        if (firstFile.path) {
            const pathParts = firstFile.path.split('/');
            pathParts.pop(); // Remove filename
            folderPath = pathParts.join('/');
        }
        // Method 2: Use webkitRelativePath and prompt for base path
        else if (firstFile.webkitRelativePath) {
            const relativePath = firstFile.webkitRelativePath;
            const rootFolder = relativePath.split('/')[0];

            // Prompt user to provide the full path
            const userPath = prompt(
                `Selected folder: "${rootFolder}"\n\nPlease enter the full path to this folder:`,
                `/Users/aviz/${rootFolder}`
            );

            if (userPath) {
                folderPath = userPath;
            } else {
                // User cancelled, just use the folder name
                folderPath = rootFolder;
            }
        }
        // Method 3: Fallback - ask for manual path
        else {
            folderPath = prompt('Please enter the full path to the folder:') || '';
        }

        document.getElementById('folderPathInput').value = folderPath;
    }
}

// Setup indexing button
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('indexFolderBtn').addEventListener('click', openIndexModal);
    document.getElementById('startIndexBtn').addEventListener('click', startIndexing);
    document.getElementById('browseFolderBtn').addEventListener('click', browseFolder);
    document.getElementById('folderBrowser').addEventListener('change', handleFolderSelection);
});

// Export functions for inline onclick handlers
window.closeModal = closeModal;
window.closeDuplicatesModal = closeDuplicatesModal;
window.openDuplicatesModal = openDuplicatesModal;
window.closeIndexModal = closeIndexModal;
window.removeTag = removeTag;
window.selectTag = selectTag;
window.createAndAddTag = createAndAddTag;
