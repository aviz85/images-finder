/**
 * Gallery Review App
 * Interactive frontend for reviewing village landscape images
 */

// State
const state = {
    images: [],
    currentPage: 1,
    totalPages: 1,
    perPage: 50,
    currentImageIndex: -1,
    filters: {
        minRating: null,
        unratedOnly: false,
        sortBy: 'semantic_score',
        order: 'desc'
    },
    searchQuery: '',
    isSearchMode: false
};

// DOM Elements
const elements = {
    galleryGrid: document.getElementById('gallery-grid'),
    loading: document.getElementById('loading'),
    pagination: document.getElementById('pagination'),
    pageInfo: document.getElementById('page-info'),
    prevPage: document.getElementById('prev-page'),
    nextPage: document.getElementById('next-page'),
    modal: document.getElementById('image-modal'),
    modalImage: document.getElementById('modal-image'),
    modalClose: document.getElementById('modal-close'),
    modalStars: document.getElementById('modal-stars'),
    clearRating: document.getElementById('clear-rating'),
    modalScore: document.getElementById('modal-score'),
    modalSize: document.getElementById('modal-size'),
    modalDimensions: document.getElementById('modal-dimensions'),
    modalPath: document.getElementById('modal-path'),
    openFinder: document.getElementById('open-finder'),
    similarGrid: document.getElementById('similar-grid'),
    modalPrev: document.getElementById('modal-prev'),
    modalNext: document.getElementById('modal-next'),
    searchInput: document.getElementById('search-input'),
    searchBtn: document.getElementById('search-btn'),
    clearSearchBtn: document.getElementById('clear-search-btn'),
    sortSelect: document.getElementById('sort-select'),
    perPageSelect: document.getElementById('per-page-select'),
    statTotal: document.getElementById('stat-total'),
    statRated: document.getElementById('stat-rated'),
    statUnrated: document.getElementById('stat-unrated')
};

// API calls
const api = {
    async getImages(params = {}) {
        const query = new URLSearchParams({
            page: params.page || state.currentPage,
            per_page: params.perPage || state.perPage,
            sort_by: state.filters.sortBy,
            order: state.filters.order,
            ...(state.filters.minRating !== null && { min_rating: state.filters.minRating }),
            ...(state.filters.unratedOnly && { unrated_only: true })
        });

        const response = await fetch(`/api/images?${query}`);
        return response.json();
    },

    async searchImages(query) {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}&top_k=200`);
        return response.json();
    },

    async rateImage(imageId, rating) {
        const response = await fetch(`/api/images/${imageId}/rate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rating })
        });
        return response.json();
    },

    async getSimilar(imageId) {
        const response = await fetch(`/api/images/${imageId}/similar?top_k=9`);
        return response.json();
    },

    async getStats() {
        const response = await fetch('/api/stats');
        return response.json();
    },

    async openFinder(path) {
        const response = await fetch(`/api/open-finder?original_path=${encodeURIComponent(path)}`, {
            method: 'POST'
        });
        return response.json();
    }
};

// Render functions
function renderGallery() {
    if (state.images.length === 0) {
        elements.galleryGrid.innerHTML = `
            <div class="empty-state">
                <h2>No images found</h2>
                <p>Try adjusting your filters or search query.</p>
            </div>
        `;
        return;
    }

    elements.galleryGrid.innerHTML = state.images.map((img, index) => `
        <div class="image-card" data-index="${index}" data-id="${img.id}">
            <img src="/thumbnails/${img.thumbnail_path}" alt="Image" loading="lazy" />
            <span class="score-badge">${(img.semantic_score || 0).toFixed(3)}</span>
            ${img.rating > 0 ? `<span class="rating-badge">${'★'.repeat(img.rating)}</span>` : ''}
        </div>
    `).join('');

    // Add click handlers
    elements.galleryGrid.querySelectorAll('.image-card').forEach(card => {
        card.addEventListener('click', () => {
            const index = parseInt(card.dataset.index);
            openModal(index);
        });
    });
}

function renderPagination() {
    elements.pageInfo.textContent = `Page ${state.currentPage} of ${state.totalPages}`;
    elements.prevPage.disabled = state.currentPage <= 1;
    elements.nextPage.disabled = state.currentPage >= state.totalPages;
    elements.pagination.style.display = state.isSearchMode ? 'none' : 'flex';
}

function renderStats(stats) {
    const total = stats.total_images || 0;
    const ratingDist = stats.rating_distribution || {};
    const unrated = ratingDist[0] || 0;
    const rated = total - unrated;

    elements.statTotal.textContent = total.toLocaleString();
    elements.statRated.textContent = rated.toLocaleString();
    elements.statUnrated.textContent = unrated.toLocaleString();
}

function renderStars(rating) {
    elements.modalStars.querySelectorAll('.star').forEach(star => {
        const starRating = parseInt(star.dataset.rating);
        star.classList.toggle('active', starRating <= rating);
    });
}

async function renderSimilar(imageId) {
    elements.similarGrid.innerHTML = '<div class="loading visible">Loading similar...</div>';

    try {
        const data = await api.getSimilar(imageId);
        if (data.similar && data.similar.length > 0) {
            elements.similarGrid.innerHTML = data.similar.map(img => `
                <div class="image-card" data-path="${img.original_path}">
                    <img src="/thumbnails/${img.thumbnail_path}" alt="Similar" loading="lazy" />
                </div>
            `).join('');

            // Add click handlers for similar images
            elements.similarGrid.querySelectorAll('.image-card').forEach(card => {
                card.addEventListener('click', () => {
                    const path = card.dataset.path;
                    const index = state.images.findIndex(img => img.original_path === path);
                    if (index >= 0) {
                        openModal(index);
                    }
                });
            });
        } else {
            elements.similarGrid.innerHTML = '<p style="color: var(--text-secondary)">No similar images found</p>';
        }
    } catch (error) {
        elements.similarGrid.innerHTML = '<p style="color: var(--text-secondary)">Error loading similar images</p>';
    }
}

// Modal functions
function openModal(index) {
    state.currentImageIndex = index;
    const img = state.images[index];

    elements.modalImage.src = `/thumbnails/${img.thumbnail_path}`;
    elements.modalScore.textContent = (img.semantic_score || 0).toFixed(4);
    elements.modalSize.textContent = img.file_size ? `${(img.file_size / 1024).toFixed(1)} KB` : '-';
    elements.modalDimensions.textContent = img.width && img.height ? `${img.width} x ${img.height}` : '-';
    elements.modalPath.textContent = img.original_path || '-';

    renderStars(img.rating || 0);
    renderSimilar(img.id);

    elements.modal.classList.add('visible');
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    elements.modal.classList.remove('visible');
    document.body.style.overflow = '';
    state.currentImageIndex = -1;
}

function navigateModal(direction) {
    const newIndex = state.currentImageIndex + direction;
    if (newIndex >= 0 && newIndex < state.images.length) {
        openModal(newIndex);
    }
}

// Data loading
async function loadImages() {
    elements.loading.classList.add('visible');

    try {
        if (state.isSearchMode && state.searchQuery) {
            const data = await api.searchImages(state.searchQuery);
            state.images = data.results || [];
            state.totalPages = 1;
            state.currentPage = 1;
        } else {
            const data = await api.getImages();
            state.images = data.images || [];
            state.totalPages = data.total_pages || 1;
        }

        renderGallery();
        renderPagination();
    } catch (error) {
        console.error('Error loading images:', error);
        elements.galleryGrid.innerHTML = `
            <div class="empty-state">
                <h2>Error loading images</h2>
                <p>${error.message}</p>
            </div>
        `;
    }

    elements.loading.classList.remove('visible');
}

async function loadStats() {
    try {
        const stats = await api.getStats();
        renderStats(stats);
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Event handlers
async function handleRate(rating) {
    if (state.currentImageIndex < 0) return;

    const img = state.images[state.currentImageIndex];
    try {
        await api.rateImage(img.id, rating);
        img.rating = rating;
        renderStars(rating);
        renderGallery(); // Update grid to show new rating
        loadStats(); // Update stats
    } catch (error) {
        console.error('Error rating image:', error);
    }
}

function handleSearch() {
    const query = elements.searchInput.value.trim();
    if (query) {
        state.searchQuery = query;
        state.isSearchMode = true;
        loadImages();
    }
}

function handleClearSearch() {
    elements.searchInput.value = '';
    state.searchQuery = '';
    state.isSearchMode = false;
    state.currentPage = 1;
    loadImages();
}

function handleRatingFilter(rating) {
    // Update active state
    document.querySelectorAll('.rating-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');

    if (rating === 'unrated') {
        state.filters.minRating = null;
        state.filters.unratedOnly = true;
    } else if (rating === 0 || rating === '0') {
        state.filters.minRating = null;
        state.filters.unratedOnly = false;
    } else {
        state.filters.minRating = parseInt(rating);
        state.filters.unratedOnly = false;
    }

    state.currentPage = 1;
    state.isSearchMode = false;
    loadImages();
}

function handleSortChange() {
    const [sortBy, order] = elements.sortSelect.value.split('-');
    state.filters.sortBy = sortBy;
    state.filters.order = order;
    state.currentPage = 1;
    loadImages();
}

function handlePerPageChange() {
    state.perPage = parseInt(elements.perPageSelect.value);
    state.currentPage = 1;
    loadImages();
}

// Initialize
function init() {
    // Pagination
    elements.prevPage.addEventListener('click', () => {
        if (state.currentPage > 1) {
            state.currentPage--;
            loadImages();
        }
    });

    elements.nextPage.addEventListener('click', () => {
        if (state.currentPage < state.totalPages) {
            state.currentPage++;
            loadImages();
        }
    });

    // Modal
    elements.modalClose.addEventListener('click', closeModal);
    elements.modal.addEventListener('click', (e) => {
        if (e.target === elements.modal) closeModal();
    });

    // Modal navigation
    elements.modalPrev.addEventListener('click', () => navigateModal(1));
    elements.modalNext.addEventListener('click', () => navigateModal(-1));

    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
        if (elements.modal.classList.contains('visible')) {
            if (e.key === 'Escape') closeModal();
            if (e.key === 'ArrowLeft') navigateModal(-1);
            if (e.key === 'ArrowRight') navigateModal(1);
            if (e.key >= '1' && e.key <= '5') handleRate(parseInt(e.key));
            if (e.key === '0') handleRate(0);
        }
    });

    // Rating stars
    elements.modalStars.querySelectorAll('.star').forEach(star => {
        star.addEventListener('click', () => {
            handleRate(parseInt(star.dataset.rating));
        });
    });

    elements.clearRating.addEventListener('click', () => handleRate(0));

    // Open in Finder
    elements.openFinder.addEventListener('click', async () => {
        if (state.currentImageIndex < 0) return;
        const img = state.images[state.currentImageIndex];
        try {
            await api.openFinder(img.original_path);
        } catch (error) {
            console.error('Error opening Finder:', error);
        }
    });

    // Search
    elements.searchBtn.addEventListener('click', handleSearch);
    elements.clearSearchBtn.addEventListener('click', handleClearSearch);
    elements.searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSearch();
    });

    // Rating filter buttons
    document.querySelectorAll('.rating-btn').forEach(btn => {
        btn.addEventListener('click', () => handleRatingFilter(btn.dataset.rating));
    });

    // Set "All" as default active
    document.querySelector('.rating-btn[data-rating="0"]').classList.add('active');

    // Sort and per page
    elements.sortSelect.addEventListener('change', handleSortChange);
    elements.perPageSelect.addEventListener('change', handlePerPageChange);

    // Load initial data
    loadImages();
    loadStats();
}

// Start app
document.addEventListener('DOMContentLoaded', init);
