/**
 * Refresh Dashboard JavaScript
 */

let dashboardData = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    await loadDashboard();
    setupEventListeners();
});

async function loadDashboard() {
    try {
        const response = await fetch('/api/refresh/dashboard', {
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });

        if (!response.ok) throw new Error('Failed to load dashboard');

        dashboardData = await response.json();
        renderDashboard();
    } catch (error) {
        console.error('Dashboard load error:', error);
        Utils.showToast('Failed to load dashboard', 'error');
    }
}

function renderDashboard() {
    renderSources();
    renderStills();
    renderPerformers();
}

function renderSources() {
    const container = document.getElementById('sources-list');
    const sources = dashboardData.sources_needing_review || [];

    if (sources.length === 0) {
        container.innerHTML = '<p class="text-still-muted text-sm">No sources need review</p>';
        document.getElementById('sources-count').textContent = '0';
        return;
    }

    container.innerHTML = sources.map(source => `
        <div class="source-item p-3 bg-still-card rounded-lg border border-still-border">
            <div class="flex justify-between items-start">
                <div>
                    <h3 class="font-medium text-still-text">${Utils.escapeHtml(source.campaign_name || 'Unnamed Source')}</h3>
                    <p class="text-sm text-still-muted">${source.still_count || 0} stills</p>
                    <p class="text-xs text-still-disabled">Review due: ${formatDate(source.review_date)}</p>
                </div>
                <div class="flex gap-2">
                    <button onclick="extendReview(${source.id})" class="btn btn-sm btn-secondary">
                        +6mo
                    </button>
                </div>
            </div>
        </div>
    `).join('');

    document.getElementById('sources-count').textContent = sources.length;
}

function renderStills() {
    const container = document.getElementById('stills-list');
    const stills = dashboardData.stills_needing_attention || {};

    const categories = [
        { key: 'duplicates', label: 'Duplicates Found', isDuplicate: true },
        { key: 'expired', label: 'Expired' },
        { key: 'needs_review', label: 'Needs Review' },
        { key: 'never_used', label: 'Never Used (30+ days)' },
        { key: 'low_performance', label: 'Low Performance' },
    ];

    let totalCount = 0;
    const html = categories.map(cat => {
        const items = stills[cat.key] || [];
        totalCount += items.length;

        if (items.length === 0) return '';

        // Special rendering for duplicates (pairs)
        if (cat.isDuplicate) {
            return `
                <div class="still-category mb-4">
                    <h3 class="text-sm font-medium text-still-amber mb-2">
                        ${cat.label} (${items.length} pairs)
                    </h3>
                    <div class="space-y-2">
                        ${items.slice(0, 5).map((pair, idx) => `
                            <div class="duplicate-item p-2 bg-still-card rounded border border-still-amber/30 cursor-pointer hover:border-still-amber transition-colors"
                                 onclick="showDuplicateComparison(${idx})">
                                <div class="flex justify-between items-center">
                                    <p class="text-sm text-still-text truncate flex-1">${Utils.escapeHtml(pair.still_a.content.substring(0, 60))}...</p>
                                    <span class="badge badge-amber text-xs ml-2">${Math.round(pair.similarity * 100)}%</span>
                                </div>
                            </div>
                        `).join('')}
                        ${items.length > 5 ? `<p class="text-xs text-still-muted">+${items.length - 5} more pairs</p>` : ''}
                    </div>
                </div>
            `;
        }

        return `
            <div class="still-category mb-4">
                <h3 class="text-sm font-medium text-still-muted mb-2">
                    ${cat.label} (${items.length})
                </h3>
                <div class="space-y-2">
                    ${items.slice(0, 5).map(still => `
                        <div class="still-item p-2 bg-still-card rounded border border-still-border cursor-pointer hover:border-still-copper transition-colors"
                             onclick="showStillDetail('${still.id}')">
                            <p class="text-sm text-still-text truncate">${Utils.escapeHtml(still.content)}</p>
                            <p class="text-xs text-still-disabled">${Utils.escapeHtml(still.still_type)} - ${Utils.escapeHtml(still.source_name || 'Unknown source')}</p>
                        </div>
                    `).join('')}
                    ${items.length > 5 ? `<p class="text-xs text-still-muted">+${items.length - 5} more</p>` : ''}
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = html || '<p class="text-still-muted text-sm">No stills need attention</p>';
    document.getElementById('stills-count').textContent = totalCount;
}

function renderPerformers() {
    const container = document.getElementById('performers-list');
    const performers = dashboardData.top_performers || [];

    if (performers.length === 0) {
        container.innerHTML = '<p class="text-still-muted text-sm">No top performers yet</p>';
        document.getElementById('performers-count').textContent = '0';
        return;
    }

    container.innerHTML = performers.map(still => `
        <div class="performer-item p-3 bg-still-card rounded-lg border border-still-border cursor-pointer hover:border-still-copper transition-colors"
             onclick="showStillDetail('${still.id}')">
            <div class="flex justify-between items-start">
                <div class="flex-1 min-w-0">
                    <p class="text-sm text-still-text truncate">${Utils.escapeHtml(still.content)}</p>
                    <p class="text-xs text-still-disabled">${Utils.escapeHtml(still.still_type)} - Used ${still.usage_count || 0}x</p>
                </div>
                ${still.performance === 'high' ? '<span class="badge badge-green text-xs">High</span>' : ''}
            </div>
        </div>
    `).join('');

    document.getElementById('performers-count').textContent = performers.length;
}

function setupEventListeners() {
    document.getElementById('run-maintenance-btn').addEventListener('click', runMaintenance);
    document.getElementById('bulk-retire-btn').addEventListener('click', bulkRetire);
    document.getElementById('bulk-extend-btn').addEventListener('click', bulkExtend);
    document.getElementById('export-csv-btn').addEventListener('click', exportCSV);
    document.getElementById('find-duplicates-btn').addEventListener('click', findDuplicates);
}

async function runMaintenance() {
    try {
        const response = await fetch('/api/refresh/run-maintenance', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });

        const data = await response.json();

        if (data.success) {
            const { results } = data;
            Utils.showToast(
                `Maintenance complete: ${results.stills_marked_needs_review} flagged, ${results.stills_retired} retired`,
                'success'
            );
            await loadDashboard();
        }
    } catch (error) {
        Utils.showToast('Maintenance failed', 'error');
    }
}

async function findDuplicates() {
    const btn = document.getElementById('find-duplicates-btn');
    const originalText = btn.textContent;
    btn.textContent = 'Scanning...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/refresh/find-duplicates', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });

        if (!response.ok) throw new Error('Scan failed');

        const data = await response.json();

        if (data.duplicates.length > 0) {
            // Add duplicates to dashboard data
            dashboardData.stills_needing_attention.duplicates = data.duplicates;
            renderStills();
            Utils.showToast(`Found ${data.duplicates.length} duplicate pairs (${data.stills_scanned} stills scanned)`, 'success');
        } else {
            Utils.showToast(`No duplicates found above ${Math.round(data.threshold_used * 100)}% similarity (${data.stills_scanned} stills scanned)`, 'info');
        }
    } catch (error) {
        console.error('Find duplicates error:', error);
        Utils.showToast('Failed to scan for duplicates', 'error');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

async function extendReview(sourceId) {
    try {
        const response = await fetch('/api/refresh/bulk-extend-review', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${getToken()}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ source_ids: [sourceId], days: 180 })
        });

        if (response.ok) {
            Utils.showToast('Review date extended by 6 months', 'success');
            await loadDashboard();
        }
    } catch (error) {
        Utils.showToast('Failed to extend review date', 'error');
    }
}

async function showStillDetail(stillId) {
    try {
        // Find the still in dashboardData
        let still = null;
        for (const cat of Object.values(dashboardData.stills_needing_attention || {})) {
            still = cat.find(s => s.id === stillId);
            if (still) break;
        }
        if (!still) {
            still = (dashboardData.top_performers || []).find(s => s.id === stillId);
        }

        if (!still) {
            Utils.showToast('Still not found', 'error');
            return;
        }

        // Fetch outputs that use this still
        let outputs = [];
        try {
            const outputsResp = await fetch(`/api/refresh/stills/${stillId}/outputs`, {
                headers: { 'Authorization': `Bearer ${getToken()}` }
            });
            if (outputsResp.ok) {
                const data = await outputsResp.json();
                outputs = data.outputs || [];
            }
        } catch (e) {
            console.debug('Failed to fetch outputs:', e);
        }

        // Render modal
        const modalBody = document.getElementById('still-modal-body');
        modalBody.innerHTML = `
            <div class="flex justify-between items-start mb-6">
                <h2 class="text-xl font-bold text-still-text">Still Detail</h2>
                <button onclick="closeStillModal()" class="btn btn-icon">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>

            <!-- Still Content -->
            <div class="bg-still-bg p-4 rounded-lg mb-6">
                <p class="text-still-text leading-relaxed">${Utils.escapeHtml(still.content)}</p>
            </div>

            <!-- Properties Grid -->
            <div class="grid grid-cols-2 gap-4 mb-6">
                <div>
                    <label class="form-label">Type</label>
                    <span class="badge badge-${getTypeBadge(still.still_type)}">${Utils.escapeHtml(still.still_type || 'Unknown')}</span>
                </div>
                <div>
                    <label class="form-label">Funnel Stage</label>
                    <span class="text-still-text">${Utils.escapeHtml(still.funnel_stage || 'Not set')}</span>
                </div>
                <div>
                    <label class="form-label">Status</label>
                    <select id="still-status" class="input-premium w-full" onchange="updateStillStatus('${stillId}', this.value)">
                        <option value="active" ${still.status === 'active' ? 'selected' : ''}>Active</option>
                        <option value="evergreen" ${still.status === 'evergreen' ? 'selected' : ''}>Evergreen</option>
                        <option value="needs_review" ${still.status === 'needs_review' ? 'selected' : ''}>Needs Review</option>
                        <option value="retired" ${still.status === 'retired' ? 'selected' : ''}>Retired</option>
                    </select>
                </div>
                <div>
                    <label class="form-label">Performance</label>
                    <select id="still-performance" class="input-premium w-full" onchange="updateStillPerformance('${stillId}', this.value)">
                        <option value="" ${!still.performance ? 'selected' : ''}>Not rated</option>
                        <option value="low" ${still.performance === 'low' ? 'selected' : ''}>Low</option>
                        <option value="medium" ${still.performance === 'medium' ? 'selected' : ''}>Medium</option>
                        <option value="high" ${still.performance === 'high' ? 'selected' : ''}>High</option>
                    </select>
                </div>
            </div>

            <!-- Expiration Info -->
            ${still.expiration_date ? `
            <div class="mb-6 p-3 rounded-lg ${isExpired(still.expiration_date) ? 'bg-error-subtle' : 'bg-still-card'}">
                <p class="text-sm ${isExpired(still.expiration_date) ? 'text-error' : 'text-still-muted'}">
                    <strong>Expiration:</strong> ${formatDate(still.expiration_date)}
                    ${still.expiration_type ? `(${still.expiration_type})` : ''}
                </p>
            </div>
            ` : ''}

            <!-- Usage Stats -->
            <div class="border-t border-still-border pt-4 mb-6">
                <h3 class="text-sm font-semibold text-still-muted mb-3 flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                    </svg>
                    USAGE STATS
                </h3>
                <p class="text-still-text">
                    Used <strong>${still.usage_count || 0}</strong> times
                    ${still.last_used_at ? ` · Last used: ${formatDate(still.last_used_at)}` : ''}
                </p>
            </div>

            <!-- Outputs Using This Still -->
            <div class="border-t border-still-border pt-4 mb-6">
                <h3 class="text-sm font-semibold text-still-muted mb-3 flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                    OUTPUTS USING THIS STILL
                </h3>
                ${outputs.length > 0 ? `
                    <div class="space-y-2">
                        ${outputs.slice(0, 5).map(output => `
                            <div class="p-2 bg-still-bg rounded flex justify-between items-center">
                                <div>
                                    <span class="badge badge-${getPlatformBadge(output.content_type)} text-xs">${Utils.escapeHtml(output.content_type)}</span>
                                    <span class="text-sm text-still-text ml-2">${formatDate(output.created_at)}</span>
                                </div>
                                <span class="text-xs text-still-muted truncate max-w-xs">${Utils.escapeHtml((output.content || '').substring(0, 50))}...</span>
                            </div>
                        `).join('')}
                        ${outputs.length > 5 ? `<p class="text-xs text-still-muted">+${outputs.length - 5} more</p>` : ''}
                    </div>
                ` : '<p class="text-sm text-still-disabled">No outputs yet</p>'}
            </div>

            <!-- Source Context -->
            ${still.source_name ? `
            <div class="border-t border-still-border pt-4">
                <h3 class="text-sm font-semibold text-still-muted mb-3 flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
                    </svg>
                    SOURCE CONTEXT
                </h3>
                <p class="text-sm text-still-text">From: <strong>${Utils.escapeHtml(still.source_name)}</strong></p>
            </div>
            ` : ''}
        `;

        document.getElementById('still-modal').classList.remove('hidden');
    } catch (error) {
        console.error('Error showing still detail:', error);
        Utils.showToast('Failed to load still details', 'error');
    }
}

async function updateStillStatus(stillId, newStatus) {
    try {
        const response = await fetch(`/api/library/${stillId}`, {
            method: 'PATCH',
            headers: {
                'Authorization': `Bearer ${getToken()}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ status: newStatus })
        });

        if (response.ok) {
            Utils.showToast('Status updated', 'success');
            await loadDashboard();
        } else {
            throw new Error('Update failed');
        }
    } catch (error) {
        Utils.showToast('Failed to update status', 'error');
    }
}

async function updateStillPerformance(stillId, newPerformance) {
    try {
        const response = await fetch(`/api/library/${stillId}`, {
            method: 'PATCH',
            headers: {
                'Authorization': `Bearer ${getToken()}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ performance: newPerformance || null })
        });

        if (response.ok) {
            Utils.showToast('Performance updated', 'success');
            await loadDashboard();
        } else {
            throw new Error('Update failed');
        }
    } catch (error) {
        Utils.showToast('Failed to update performance', 'error');
    }
}

function getTypeBadge(type) {
    const badges = {
        'data': 'data',
        'story': 'story',
        'insight': 'insight',
        'problem': 'problem',
        'solution': 'solution',
        'quote': 'quote'
    };
    return badges[type?.toLowerCase()] || 'muted';
}

function getPlatformBadge(platform) {
    const badges = {
        'linkedin': 'info',
        'twitter': 'info',
        'email': 'muted'
    };
    return badges[platform?.toLowerCase()] || 'muted';
}

function isExpired(dateStr) {
    if (!dateStr) return false;
    return new Date(dateStr) < new Date();
}

async function bulkRetire() {
    const expiredStills = (dashboardData.stills_needing_attention?.expired || []).map(s => s.id);

    if (expiredStills.length === 0) {
        Utils.showToast('No expired stills to retire', 'info');
        return;
    }

    try {
        const response = await fetch('/api/refresh/bulk-retire', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${getToken()}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ still_ids: expiredStills })
        });

        if (response.ok) {
            Utils.showToast(`Retired ${expiredStills.length} stills`, 'success');
            await loadDashboard();
        }
    } catch (error) {
        Utils.showToast('Failed to retire stills', 'error');
    }
}

async function bulkExtend() {
    const sourceIds = (dashboardData.sources_needing_review || []).map(s => s.id);

    if (sourceIds.length === 0) {
        Utils.showToast('No sources to extend', 'info');
        return;
    }

    try {
        const response = await fetch('/api/refresh/bulk-extend-review', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${getToken()}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ source_ids: sourceIds, days: 180 })
        });

        if (response.ok) {
            Utils.showToast(`Extended ${sourceIds.length} source review dates`, 'success');
            await loadDashboard();
        }
    } catch (error) {
        Utils.showToast('Failed to extend review dates', 'error');
    }
}

async function exportCSV() {
    try {
        const response = await fetch('/api/refresh/export-stale', {
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'stale_content.csv';
        a.click();
        window.URL.revokeObjectURL(url);

        Utils.showToast('CSV exported', 'success');
    } catch (error) {
        Utils.showToast('Export failed', 'error');
    }
}

function closeStillModal() {
    document.getElementById('still-modal').classList.add('hidden');
}

function formatDate(dateStr) {
    if (!dateStr) return 'Unknown';
    const date = new Date(dateStr);
    return date.toLocaleDateString();
}

function getToken() {
    return localStorage.getItem('auth_token') || '';
}

function showDuplicateComparison(pairIndex) {
    const pairs = dashboardData.stills_needing_attention.duplicates || [];
    if (pairIndex >= pairs.length) return;

    const pair = pairs[pairIndex];
    const modal = document.getElementById('duplicate-modal');
    const body = document.getElementById('duplicate-modal-body');

    body.innerHTML = `
        <p class="text-still-amber text-center mb-4 font-medium">${Math.round(pair.similarity * 100)}% similar</p>
        <div class="grid grid-cols-2 gap-4">
            <!-- Still A -->
            <div class="border border-still-border rounded-lg p-4">
                <h3 class="font-semibold text-still-text mb-3">Still A</h3>
                <div class="space-y-2 text-sm">
                    <p><span class="text-still-muted">Created:</span> <span class="text-still-text">${formatDate(pair.still_a.created_at)}</span></p>
                    <p><span class="text-still-muted">Type:</span> <span class="text-still-text">${Utils.escapeHtml(pair.still_a.still_type)}</span></p>
                    <p><span class="text-still-muted">Used:</span> <span class="text-still-text">${pair.still_a.usage_count || 0} times</span></p>
                    <p><span class="text-still-muted">Source:</span> <span class="text-still-text">${Utils.escapeHtml(pair.still_a.source_file || 'Unknown')}</span></p>
                </div>
                <div class="mt-4 p-3 bg-still-bg rounded text-still-text text-sm max-h-40 overflow-y-auto">
                    ${Utils.escapeHtml(pair.still_a.content)}
                </div>
                <button onclick="mergeDuplicates('${pair.still_a.id}', '${pair.still_b.id}', ${pairIndex})"
                        class="mt-4 w-full btn btn-primary">
                    Keep This One
                </button>
            </div>

            <!-- Still B -->
            <div class="border border-still-border rounded-lg p-4">
                <h3 class="font-semibold text-still-text mb-3">Still B</h3>
                <div class="space-y-2 text-sm">
                    <p><span class="text-still-muted">Created:</span> <span class="text-still-text">${formatDate(pair.still_b.created_at)}</span></p>
                    <p><span class="text-still-muted">Type:</span> <span class="text-still-text">${Utils.escapeHtml(pair.still_b.still_type)}</span></p>
                    <p><span class="text-still-muted">Used:</span> <span class="text-still-text">${pair.still_b.usage_count || 0} times</span></p>
                    <p><span class="text-still-muted">Source:</span> <span class="text-still-text">${Utils.escapeHtml(pair.still_b.source_file || 'Unknown')}</span></p>
                </div>
                <div class="mt-4 p-3 bg-still-bg rounded text-still-text text-sm max-h-40 overflow-y-auto">
                    ${Utils.escapeHtml(pair.still_b.content)}
                </div>
                <button onclick="mergeDuplicates('${pair.still_b.id}', '${pair.still_a.id}', ${pairIndex})"
                        class="mt-4 w-full btn btn-primary">
                    Keep This One
                </button>
            </div>
        </div>
        <div class="mt-4 text-center">
            <button onclick="skipDuplicate(${pairIndex})" class="btn btn-secondary">
                Skip - Not Duplicates
            </button>
        </div>
    `;

    modal.classList.remove('hidden');
}

function closeDuplicateModal() {
    document.getElementById('duplicate-modal').classList.add('hidden');
}

async function mergeDuplicates(winnerId, loserId, pairIndex) {
    // Disable all buttons in modal immediately to prevent double-clicks
    const buttons = document.querySelectorAll('#duplicate-modal button');
    buttons.forEach(btn => btn.disabled = true);

    try {
        const response = await fetch('/api/refresh/merge-duplicates', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${getToken()}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ winner_id: winnerId, loser_id: loserId })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Merge failed');
        }

        // Remove pair from list
        dashboardData.stills_needing_attention.duplicates.splice(pairIndex, 1);

        // If no more duplicates, remove the category
        if (dashboardData.stills_needing_attention.duplicates.length === 0) {
            delete dashboardData.stills_needing_attention.duplicates;
        }

        renderStills();
        closeDuplicateModal();
        Utils.showToast('Merged - 1 still retired', 'success');
    } catch (error) {
        console.error('Merge error:', error);

        // Log to database for production debugging
        if (typeof ErrorLogger !== 'undefined') {
            ErrorLogger.log('api_error', error.message, '/api/refresh/merge-duplicates', error.stack, {
                winner_id: winnerId,
                loser_id: loserId
            });
        }

        // Show friendly message to user
        const friendlyMessage = typeof ErrorLogger !== 'undefined'
            ? ErrorLogger.friendlyMessage(error.message)
            : error.message;
        Utils.showToast(friendlyMessage, 'error');

        // Close modal since the pair is probably already processed
        closeDuplicateModal();

        // Refresh the duplicates list to get fresh data
        await findDuplicates();
    } finally {
        buttons.forEach(btn => btn.disabled = false);
    }
}

function skipDuplicate(pairIndex) {
    // Just remove from current view without merging
    dashboardData.stills_needing_attention.duplicates.splice(pairIndex, 1);

    if (dashboardData.stills_needing_attention.duplicates.length === 0) {
        delete dashboardData.stills_needing_attention.duplicates;
    }

    renderStills();
    closeDuplicateModal();
    Utils.showToast('Skipped - pair removed from list', 'info');
}
