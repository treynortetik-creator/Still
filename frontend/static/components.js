// Premium Navigation Component
function renderPremiumNav(activePage = '') {
    const navLinks = [
        { href: '/upload.html', label: 'Distill' },
        { href: '/reserve.html', label: 'Reserve' },
        { href: '/refresh.html', label: 'Refresh', hasBadge: true },
        { href: '/workshop.html', label: 'Workshop' },
        { href: '/calendar.html', label: 'Calendar' },
        // { href: '/autopilot.html', label: 'Autopilot' },  // Hidden for MVP - feature ready for future
        { href: '/settings.html', label: 'Settings' },
    ];

    const linksHtml = navLinks.map(link => {
        const isActive = link.href.includes(activePage);
        const badgeHtml = link.hasBadge ? '<span class="nav-badge" id="refresh-badge" style="display: none;">0</span>' : '';
        return `<a href="${link.href}" class="nav-link${isActive ? ' active' : ''}">${link.label}${badgeHtml}</a>`;
    }).join('');

    return `
        <nav class="nav-premium">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="flex justify-between h-16">
                    <div class="flex items-center space-x-8">
                        <a href="/" class="flex items-center">
                            <img src="/static/images/Still Logo.svg" alt="Still" class="h-12">
                        </a>
                        <div class="hidden md:flex space-x-1">
                            ${linksHtml}
                        </div>
                    </div>
                    <div class="flex items-center space-x-3">
                        <button onclick="ThemeManager.toggle()" class="theme-toggle-premium" title="Toggle light/dark mode">
                            <svg class="theme-icon-sun w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
                            </svg>
                            <svg class="theme-icon-moon hidden w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/>
                            </svg>
                        </button>
                        <div id="navbar-user" class="flex items-center"></div>
                    </div>
                </div>
            </div>
        </nav>
    `;
}

// Fetch and update refresh badge count
async function updateRefreshBadge() {
    try {
        const response = await fetch('/api/refresh/counts', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('auth_token') || ''}`
            }
        });
        if (!response.ok) return;

        const data = await response.json();
        const totalCount = (data.sources || 0) + (data.stills || 0);

        const badge = document.getElementById('refresh-badge');
        if (badge) {
            if (totalCount > 0) {
                badge.textContent = totalCount > 99 ? '99+' : totalCount;
                badge.style.display = 'inline-flex';
            } else {
                badge.style.display = 'none';
            }
        }
    } catch (error) {
        // Silently fail - badge is non-critical
        console.debug('Failed to fetch refresh counts:', error);
    }
}

// Initialize navigation on page load
document.addEventListener('DOMContentLoaded', () => {
    const navContainer = document.getElementById('nav-container');
    if (navContainer) {
        const currentPage = window.location.pathname.split('/').pop().replace('.html', '');
        navContainer.innerHTML = renderPremiumNav(currentPage);

        // Update theme icons after nav is rendered
        if (typeof ThemeManager !== 'undefined') {
            ThemeManager.updateToggleIcons(ThemeManager.getTheme());
        }

        // Update auth navbar
        if (typeof Auth !== 'undefined' && Auth.updateNavbar) {
            Auth.updateNavbar();
        }

        // Fetch refresh badge count
        updateRefreshBadge();
    }
});
