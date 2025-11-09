// Global state
let currentPage = 1;
let currentImageId = null;
let searchTimeout = null;
let searchMode = 'browse';  // 'browse', 'text', or 'image'
let searchQuery = null;     // text string or image_id

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadImages();
    loadStats();
    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    // Search
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

    // Controls
    document.getElementById('sortBy').addEventListener('change', () => loadImages());
    document.getElementById('sortOrder').addEventListener('change', () => loadImages());
    document.getElementById('minRating').addEventListener('change', () => loadImages());
    document.getElementById('perPage').addEventListener('change', () => {
        currentPage = 1;
        loadImages();
    });
    document.getElementById('refreshBtn').addEventListener('click', () => {
        currentPage = 1;
        loadImages();
        loadStats();
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
            try {
                const response = await fetch(`/image/${currentImageId}`);
                const imageData = await response.json();

                // Close modal
                closeModal();

                // Start similarity search
                setTimeout(() => {
                    searchBySimilarImage(currentImageId, imageData.file_name);
                }, 100);
            } catch (error) {
                console.error('Error starting similarity search:', error);
                showToast('Failed to start similarity search', 'error');
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
    const stars = createStarDisplay(rating);

    // Handle both 'id' (from browse) and 'image_id' (from search)
    const imageId = image.id || image.image_id;

    // Create folder chips HTML
    const folders = image.folders || [];
    const folderChipsHtml = folders.length > 0
        ? `<div class="folder-tags">${folders.map(f => `<span class="folder-chip" title="${f}">${f}</span>`).join('')}</div>`
        : '';

    card.innerHTML = `
        <div class="image-wrapper">
            <img src="/thumbnail/${imageId}" alt="${image.file_name}" loading="lazy">
        </div>
        <div class="image-info">
            <div class="image-name" title="${image.file_name}">${image.file_name}</div>
            <div class="image-meta">
                <span>${image.width} × ${image.height}</span>
                <div class="rating-display">${stars}</div>
            </div>
            ${folderChipsHtml}
        </div>
    `;

    return card;
}

// Create star display
function createStarDisplay(rating) {
    let html = '';
    for (let i = 1; i <= 5; i++) {
        const filled = i <= rating ? 'filled' : '';
        html += `<span class="star ${filled}">★</span>`;
    }
    return html;
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

// Export functions for inline onclick handlers
window.closeModal = closeModal;
