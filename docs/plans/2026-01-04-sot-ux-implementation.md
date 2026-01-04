# Source of Truth UX Improvements - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add split-view after SOT approval showing live processing, and add SOT view/edit modal to Library page.

**Architecture:** Frontend-only changes. Results page gets split-view layout with status polling. Library page gets SOT button per card that opens a reusable modal component.

**Tech Stack:** HTML, Tailwind CSS, vanilla JavaScript, existing API endpoints

---

## Task 1: Add Split View CSS to results.html

**Files:**
- Modify: `frontend/results.html:42-66` (style section)

**Step 1: Add split-view CSS**

Add after line 65 (before closing `</style>`):

```css
/* Split View for post-approval processing */
.split-view-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    min-height: 60vh;
}
.split-view-left {
    overflow-y: auto;
    max-height: 70vh;
    padding-right: 1rem;
}
.split-view-right {
    border-left: 1px solid var(--still-border);
    padding-left: 1.5rem;
}
@media (max-width: 768px) {
    .split-view-container {
        grid-template-columns: 1fr;
    }
    .split-view-right {
        border-left: none;
        border-top: 1px solid var(--still-border);
        padding-left: 0;
        padding-top: 1.5rem;
    }
}
.status-step { display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0; }
.status-step-icon { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: 50%; }
.status-step-pending { background: var(--still-border); color: var(--still-muted); }
.status-step-active { background: var(--still-copper); color: white; }
.status-step-complete { background: var(--still-green); color: white; }
```

**Step 2: Verify CSS added**

Open `frontend/results.html` and verify the new styles are present.

**Step 3: Commit**

```bash
git add frontend/results.html
git commit -m "feat(results): add split-view CSS for post-approval processing"
```

---

## Task 2: Add Split View HTML Structure to results.html

**Files:**
- Modify: `frontend/results.html:116-180` (source-of-truth-section)

**Step 1: Wrap SOT section in split-view container**

Replace the source-of-truth-section with a split-view wrapper. After line 115, the section should become:

```html
<!-- Split View Container (shown after approval during processing) -->
<div id="split-view-wrapper" class="hidden mb-6">
    <div class="split-view-container">
        <!-- Left: Source of Truth (read-only) -->
        <div class="split-view-left">
            <div class="bg-still-card rounded-lg shadow-md p-6 border border-still-border">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-xl font-bold text-still-text flex items-center gap-2">
                        <svg class="w-5 h-5 text-still-copper" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                        </svg>
                        Source of Truth
                    </h2>
                    <span class="text-sm px-2 py-1 rounded bg-still-green/20 text-still-green">Approved</span>
                </div>
                <div id="split-sot-content" class="space-y-4 text-sm">
                    <!-- Populated by JS -->
                </div>
            </div>
        </div>

        <!-- Right: Processing Status -->
        <div class="split-view-right">
            <div class="bg-still-card rounded-lg shadow-md p-6 border border-still-border">
                <h2 class="text-xl font-bold text-still-text mb-4">Processing Content</h2>

                <!-- Progress Bar -->
                <div class="mb-6">
                    <div class="flex justify-between text-sm mb-2">
                        <span id="split-current-step" class="text-still-muted">Initializing...</span>
                        <span id="split-progress-percent" class="text-still-copper font-semibold">0%</span>
                    </div>
                    <div class="w-full bg-still-border rounded-full h-2">
                        <div id="split-progress-bar" class="copper-gradient h-2 rounded-full transition-all duration-500" style="width: 0%"></div>
                    </div>
                </div>

                <!-- Processing Steps -->
                <div id="split-steps" class="space-y-2">
                    <div class="status-step" data-step="distilling">
                        <div class="status-step-icon status-step-pending">
                            <span class="text-xs">1</span>
                        </div>
                        <span class="text-still-muted">Distilling content stills</span>
                    </div>
                    <div class="status-step" data-step="drafting">
                        <div class="status-step-icon status-step-pending">
                            <span class="text-xs">2</span>
                        </div>
                        <span class="text-still-muted">Drafting content</span>
                    </div>
                    <div class="status-step" data-step="editing">
                        <div class="status-step-icon status-step-pending">
                            <span class="text-xs">3</span>
                        </div>
                        <span class="text-still-muted">Editing for audience</span>
                    </div>
                    <div class="status-step" data-step="factchecking">
                        <div class="status-step-icon status-step-pending">
                            <span class="text-xs">4</span>
                        </div>
                        <span class="text-still-muted">Fact-checking</span>
                    </div>
                </div>

                <!-- Completion Message (hidden until complete) -->
                <div id="split-complete" class="hidden mt-6 p-4 bg-still-green/10 rounded-lg border border-still-green/30">
                    <p class="text-still-green font-semibold mb-2">Processing Complete!</p>
                    <button onclick="window.location.reload()" class="btn btn-primary text-white px-4 py-2 rounded-lg">
                        View Results
                    </button>
                </div>

                <!-- Error Message (hidden unless error) -->
                <div id="split-error" class="hidden mt-6 p-4 bg-still-error/10 rounded-lg border border-still-error/30">
                    <p class="text-still-error font-semibold mb-2">Processing Failed</p>
                    <p id="split-error-message" class="text-still-muted text-sm mb-3"></p>
                    <button onclick="window.location.reload()" class="px-4 py-2 border border-still-border rounded-lg text-still-text hover:bg-still-border">
                        Refresh Page
                    </button>
                </div>
            </div>
        </div>
    </div>
</div>
```

**Step 2: Verify HTML structure**

Check that the new `split-view-wrapper` div is in place.

**Step 3: Commit**

```bash
git add frontend/results.html
git commit -m "feat(results): add split-view HTML structure"
```

---

## Task 3: Add Split View JavaScript Logic to results.html

**Files:**
- Modify: `frontend/results.html:368-390` (approveSourceOfTruth function)

**Step 1: Replace approveSourceOfTruth function**

Replace the existing `approveSourceOfTruth` function with:

```javascript
async function approveSourceOfTruth() {
    try {
        const response = await Auth.fetchWithAuth(`/api/jobs/${jobId}/approve-source`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Failed to approve');

        showToast('Source of Truth approved! Pipeline resuming...');

        // Update UI - hide approval actions
        document.getElementById('sot-approval-actions').classList.add('hidden');
        const badge = document.getElementById('sot-approval-badge');
        badge.textContent = 'Approved';
        badge.className = 'text-sm px-2 py-1 rounded bg-still-green/20 text-still-green';

        // Switch to split view mode
        activateSplitView();
    } catch (err) {
        showToast('Error approving Source of Truth');
        console.error('Error approving Source of Truth:', err);
    }
}

function activateSplitView() {
    // Hide the regular SOT section
    document.getElementById('source-of-truth-section').classList.add('hidden');

    // Show split view
    const splitWrapper = document.getElementById('split-view-wrapper');
    splitWrapper.classList.remove('hidden');

    // Populate left panel with SOT summary
    populateSplitSOT();

    // Start polling for status
    startSplitViewPolling();
}

function populateSplitSOT() {
    const content = document.getElementById('split-sot-content');
    if (!currentSource) return;

    content.innerHTML = `
        <div>
            <h4 class="font-semibold text-still-text mb-1">Core Narratives</h4>
            <ul class="list-disc list-inside text-still-muted">
                ${currentSource.core_narratives?.slice(0, 3).map(n =>
                    `<li>${escapeHtml(n.narrative)}</li>`
                ).join('') || '<li>None</li>'}
            </ul>
        </div>
        <div>
            <h4 class="font-semibold text-still-text mb-1">Pain Point</h4>
            <p class="text-still-muted">${escapeHtml(currentSource.primary_pain_point || 'Not specified')}</p>
        </div>
        <div>
            <h4 class="font-semibold text-still-text mb-1">Promise</h4>
            <p class="text-still-muted">${escapeHtml(currentSource.the_promise || 'Not specified')}</p>
        </div>
        <div>
            <h4 class="font-semibold text-still-text mb-1">Statistics</h4>
            <p class="text-still-disabled">${currentSource.statistics?.length || 0} extracted</p>
        </div>
        <div>
            <h4 class="font-semibold text-still-text mb-1">Funnel Stage</h4>
            <p class="text-still-muted capitalize">${escapeHtml(currentSource.funnel_stage || 'Not specified')}</p>
        </div>
    `;
}

let splitPollInterval = null;

function startSplitViewPolling() {
    // Poll every 3 seconds
    splitPollInterval = setInterval(pollSplitStatus, 3000);
    // Also poll immediately
    pollSplitStatus();
}

async function pollSplitStatus() {
    try {
        const response = await Auth.fetchWithAuth(`/api/job/${jobId}/status`);
        if (!response.ok) throw new Error('Failed to fetch status');

        const data = await response.json();
        updateSplitViewStatus(data);

        if (data.status === 'complete') {
            clearInterval(splitPollInterval);
            document.getElementById('split-complete').classList.remove('hidden');
        } else if (data.status === 'failed') {
            clearInterval(splitPollInterval);
            document.getElementById('split-error').classList.remove('hidden');
            document.getElementById('split-error-message').textContent = data.error || 'An error occurred';
        }
    } catch (err) {
        console.error('Split view poll error:', err);
    }
}

function updateSplitViewStatus(data) {
    // Update progress bar
    document.getElementById('split-current-step').textContent = data.current_step || 'Processing...';
    document.getElementById('split-progress-percent').textContent = `${data.progress || 0}%`;
    document.getElementById('split-progress-bar').style.width = `${data.progress || 0}%`;

    // Update step indicators
    const stepOrder = ['distilling', 'drafting', 'editing', 'factchecking'];
    const currentStepIndex = stepOrder.indexOf(data.status);

    document.querySelectorAll('#split-steps .status-step').forEach((stepEl, index) => {
        const icon = stepEl.querySelector('.status-step-icon');
        const text = stepEl.querySelector('span:last-child');

        icon.classList.remove('status-step-pending', 'status-step-active', 'status-step-complete');

        if (index < currentStepIndex) {
            // Complete
            icon.classList.add('status-step-complete');
            icon.innerHTML = '<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>';
            text.classList.remove('text-still-muted');
            text.classList.add('text-still-green');
        } else if (index === currentStepIndex) {
            // Active
            icon.classList.add('status-step-active');
            icon.innerHTML = '<div class="w-2 h-2 bg-white rounded-full animate-pulse"></div>';
            text.classList.remove('text-still-muted');
            text.classList.add('text-still-copper', 'font-semibold');
        } else {
            // Pending
            icon.classList.add('status-step-pending');
            icon.innerHTML = `<span class="text-xs">${index + 1}</span>`;
            text.classList.add('text-still-muted');
            text.classList.remove('text-still-copper', 'text-still-green', 'font-semibold');
        }
    });
}
```

**Step 2: Add currentSource variable declaration**

Near the top of the script (around line 268), add after `let jobId = ...`:

```javascript
let currentSource = null;
```

**Step 3: Store source data when loaded**

In the existing `loadResults` function, after `renderSourceOfTruth(source)`, add:

```javascript
currentSource = source;
```

**Step 4: Verify JS logic**

Check that all new functions are in place and `currentSource` is being set.

**Step 5: Commit**

```bash
git add frontend/results.html
git commit -m "feat(results): add split-view JavaScript logic with polling"
```

---

## Task 4: Add SOT Modal HTML to library.html

**Files:**
- Modify: `frontend/library.html:176-181` (before Copy Toast)

**Step 1: Add SOT modal HTML**

Insert before the Copy Toast div (around line 177):

```html
<!-- Source of Truth Modal -->
<div id="sot-modal" class="hidden fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
    <div class="bg-still-card rounded-lg shadow-xl max-w-3xl w-full mx-4 max-h-[90vh] flex flex-col border border-still-border">
        <!-- Modal Header -->
        <div class="p-4 border-b border-still-border flex justify-between items-center">
            <div>
                <h2 id="sot-modal-title" class="text-xl font-bold text-still-text">Source of Truth</h2>
                <div class="flex items-center gap-2 mt-1">
                    <span id="sot-modal-badge" class="text-xs px-2 py-0.5 rounded"></span>
                    <span id="sot-modal-review-date" class="text-xs text-still-disabled"></span>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <button id="sot-edit-toggle" onclick="toggleSOTEdit()" class="px-3 py-1 text-sm border border-still-border rounded hover:bg-still-border text-still-muted">
                    Edit
                </button>
                <button onclick="closeSOTModal()" class="text-still-muted hover:text-still-text text-2xl">&times;</button>
            </div>
        </div>

        <!-- Modal Body (scrollable) -->
        <div class="p-6 overflow-y-auto flex-1">
            <div id="sot-modal-content" class="space-y-6">
                <!-- Core Narratives -->
                <div>
                    <h3 class="font-semibold text-still-text mb-2">Core Narratives</h3>
                    <div id="sot-modal-narratives" class="space-y-2"></div>
                </div>

                <!-- Statistics -->
                <div>
                    <h3 class="font-semibold text-still-text mb-2">Statistics</h3>
                    <div class="overflow-x-auto">
                        <table class="w-full text-sm">
                            <thead>
                                <tr class="border-b border-still-border">
                                    <th class="text-left px-2 py-1 text-still-muted">Stat</th>
                                    <th class="text-left px-2 py-1 text-still-muted">Citation</th>
                                    <th class="text-left px-2 py-1 text-still-muted">Confidence</th>
                                </tr>
                            </thead>
                            <tbody id="sot-modal-statistics"></tbody>
                        </table>
                    </div>
                </div>

                <!-- Quotable Moments -->
                <div>
                    <h3 class="font-semibold text-still-text mb-2">Quotable Moments</h3>
                    <div id="sot-modal-quotes" class="space-y-2"></div>
                </div>

                <!-- Pain Point & Promise -->
                <div class="grid md:grid-cols-2 gap-4">
                    <div>
                        <h3 class="font-semibold text-still-text mb-2">Primary Pain Point</h3>
                        <p id="sot-modal-pain-point" class="text-still-muted"></p>
                    </div>
                    <div>
                        <h3 class="font-semibold text-still-text mb-2">The Promise</h3>
                        <p id="sot-modal-promise" class="text-still-muted"></p>
                    </div>
                </div>

                <!-- Funnel Stage -->
                <div>
                    <h3 class="font-semibold text-still-text mb-2">Funnel Stage</h3>
                    <span id="sot-modal-funnel" class="px-3 py-1 bg-still-border rounded-full text-sm text-still-muted capitalize"></span>
                </div>
            </div>

            <!-- Edit Form (hidden by default) -->
            <div id="sot-edit-form" class="hidden space-y-4">
                <div>
                    <label class="block text-sm font-medium text-still-text mb-1">Primary Pain Point</label>
                    <textarea id="edit-pain-point" rows="2" class="w-full input-premium"></textarea>
                </div>
                <div>
                    <label class="block text-sm font-medium text-still-text mb-1">The Promise</label>
                    <textarea id="edit-promise" rows="2" class="w-full input-premium"></textarea>
                </div>
                <div>
                    <label class="block text-sm font-medium text-still-text mb-1">Funnel Stage</label>
                    <select id="edit-funnel" class="input-premium select-premium">
                        <option value="awareness">Awareness</option>
                        <option value="consideration">Consideration</option>
                        <option value="decision">Decision</option>
                    </select>
                </div>
            </div>
        </div>

        <!-- Modal Footer -->
        <div class="p-4 border-t border-still-border flex justify-end gap-3">
            <button onclick="closeSOTModal()" class="px-4 py-2 border border-still-border rounded-lg text-still-text hover:bg-still-border transition">
                Close
            </button>
            <button id="sot-save-btn" onclick="saveSOTChanges()" class="hidden px-4 py-2 btn btn-primary text-white rounded-lg transition">
                Save Changes
            </button>
        </div>
    </div>
</div>
```

**Step 2: Verify modal HTML added**

Check that the `sot-modal` div is in place.

**Step 3: Commit**

```bash
git add frontend/library.html
git commit -m "feat(library): add SOT modal HTML structure"
```

---

## Task 5: Add SOT Button to Library Cards

**Files:**
- Modify: `frontend/library.html:275-291` (card.innerHTML in renderLibrary)

**Step 1: Update card HTML to include SOT button**

Replace the card.innerHTML section with:

```javascript
card.innerHTML = `
    <div class="flex justify-between items-start mb-2">
        <span class="text-xs font-semibold ${textClass} uppercase">${entry.entry_type}</span>
        <div class="flex items-center gap-2">
            ${entry.source_id ? `
                <button onclick="event.stopPropagation(); openSOTModal('${entry.job_id}', ${entry.source_id}, ${entry.source_approved || false})"
                    class="text-xs px-2 py-1 rounded ${entry.source_approved ? 'bg-still-copper/20 text-still-copper' : 'bg-still-amber/20 text-still-amber'} hover:opacity-80"
                    title="View Source of Truth">
                    SOT
                </button>
            ` : ''}
            <input type="checkbox" ${isSelected ? 'checked' : ''}
              class="rounded border-still-border input-premium" onclick="event.stopPropagation(); toggleSelect(${entry.id}, '${entry.content.replace(/'/g, "\\'")}')">
        </div>
    </div>
    <p class="text-still-text text-sm line-clamp-3">${escapeHtml(entry.content)}</p>
    <div class="mt-3 flex flex-wrap gap-1">
        ${entry.tags && entry.tags.length ? entry.tags.slice(0, 3).map(tag =>
            `<span class="text-xs px-2 py-0.5 bg-still-border text-still-muted rounded">${escapeHtml(tag)}</span>`
        ).join('') : ''}
    </div>
    <div class="mt-2 flex justify-between text-xs text-still-disabled">
        <span>Used ${entry.times_used || 0}x</span>
        ${relevance ? `<span>${relevance}</span>` : ''}
    </div>
`;
```

**Step 2: Verify card HTML updated**

Check that SOT button is conditionally rendered.

**Step 3: Commit**

```bash
git add frontend/library.html
git commit -m "feat(library): add SOT button to library cards"
```

---

## Task 6: Add SOT Modal JavaScript to library.html

**Files:**
- Modify: `frontend/library.html` (end of script section, before closing `</script>`)

**Step 1: Add modal JavaScript functions**

Add before the closing `</script>` tag:

```javascript
// SOT Modal State
let currentSOTJobId = null;
let currentSOTData = null;
let sotEditMode = false;

async function openSOTModal(jobId, sourceId, isApproved) {
    currentSOTJobId = jobId;

    try {
        const response = await Auth.fetchWithAuth(`/api/jobs/${jobId}/source`);
        if (!response.ok) {
            if (response.status === 404) {
                showToast('Source of Truth not found');
                return;
            }
            throw new Error('Failed to load Source of Truth');
        }

        currentSOTData = await response.json();
        renderSOTModal(currentSOTData, isApproved);
        document.getElementById('sot-modal').classList.remove('hidden');
    } catch (err) {
        console.error('Error loading SOT:', err);
        showToast('Error loading Source of Truth');
    }
}

function renderSOTModal(source, isApproved) {
    // Title
    document.getElementById('sot-modal-title').textContent = 'Source of Truth';

    // Badge
    const badge = document.getElementById('sot-modal-badge');
    if (isApproved) {
        badge.textContent = 'Approved';
        badge.className = 'text-xs px-2 py-0.5 rounded bg-still-green/20 text-still-green';
    } else {
        badge.textContent = 'Pending';
        badge.className = 'text-xs px-2 py-0.5 rounded bg-still-amber/20 text-still-amber';
    }

    // Review date
    document.getElementById('sot-modal-review-date').textContent =
        source.review_date ? `Review: ${source.review_date}` : '';

    // Core Narratives
    const narrativesEl = document.getElementById('sot-modal-narratives');
    if (source.core_narratives?.length) {
        narrativesEl.innerHTML = source.core_narratives.map(n => `
            <div class="p-2 bg-still-bg rounded border border-still-border">
                <p class="text-still-muted">${escapeHtml(n.narrative)}</p>
                <p class="text-xs text-still-disabled mt-1">${escapeHtml(n.supporting_evidence || '')}</p>
            </div>
        `).join('');
    } else {
        narrativesEl.innerHTML = '<p class="text-still-disabled">No narratives</p>';
    }

    // Statistics
    const statsEl = document.getElementById('sot-modal-statistics');
    if (source.statistics?.length) {
        statsEl.innerHTML = source.statistics.map(s => `
            <tr class="border-b border-still-border">
                <td class="px-2 py-1 text-still-muted">${escapeHtml(s.stat)}</td>
                <td class="px-2 py-1 text-still-disabled">${escapeHtml(s.citation || '-')}</td>
                <td class="px-2 py-1">
                    <span class="text-xs px-1.5 py-0.5 rounded ${getConfidenceClass(s.confidence)}">${s.confidence || 'unknown'}</span>
                </td>
            </tr>
        `).join('');
    } else {
        statsEl.innerHTML = '<tr><td colspan="3" class="text-still-disabled py-2">No statistics</td></tr>';
    }

    // Quotes
    const quotesEl = document.getElementById('sot-modal-quotes');
    if (source.quotable_moments?.length) {
        quotesEl.innerHTML = source.quotable_moments.map(q => `
            <blockquote class="border-l-2 border-still-copper pl-3 py-1">
                <p class="text-still-muted italic">"${escapeHtml(q.quote)}"</p>
                <footer class="text-xs text-still-disabled mt-1">— ${escapeHtml(q.speaker || 'Unknown')}</footer>
            </blockquote>
        `).join('');
    } else {
        quotesEl.innerHTML = '<p class="text-still-disabled">No quotes</p>';
    }

    // Pain Point & Promise
    document.getElementById('sot-modal-pain-point').textContent = source.primary_pain_point || 'Not specified';
    document.getElementById('sot-modal-promise').textContent = source.the_promise || 'Not specified';

    // Funnel
    document.getElementById('sot-modal-funnel').textContent = source.funnel_stage || 'Not specified';

    // Populate edit form values
    document.getElementById('edit-pain-point').value = source.primary_pain_point || '';
    document.getElementById('edit-promise').value = source.the_promise || '';
    document.getElementById('edit-funnel').value = source.funnel_stage || 'awareness';

    // Reset edit mode
    sotEditMode = false;
    document.getElementById('sot-modal-content').classList.remove('hidden');
    document.getElementById('sot-edit-form').classList.add('hidden');
    document.getElementById('sot-save-btn').classList.add('hidden');
    document.getElementById('sot-edit-toggle').textContent = 'Edit';
}

function getConfidenceClass(confidence) {
    switch (confidence) {
        case 'verified': return 'bg-still-green/20 text-still-green';
        case 'calculated': return 'bg-still-copper/20 text-still-copper';
        case 'implied': return 'bg-still-amber/20 text-still-amber';
        default: return 'bg-still-border text-still-muted';
    }
}

function closeSOTModal() {
    document.getElementById('sot-modal').classList.add('hidden');
    currentSOTJobId = null;
    currentSOTData = null;
    sotEditMode = false;
}

function toggleSOTEdit() {
    sotEditMode = !sotEditMode;
    document.getElementById('sot-modal-content').classList.toggle('hidden', sotEditMode);
    document.getElementById('sot-edit-form').classList.toggle('hidden', !sotEditMode);
    document.getElementById('sot-save-btn').classList.toggle('hidden', !sotEditMode);
    document.getElementById('sot-edit-toggle').textContent = sotEditMode ? 'Cancel' : 'Edit';
}

async function saveSOTChanges() {
    if (!currentSOTJobId) return;

    const updates = {
        primary_pain_point: document.getElementById('edit-pain-point').value,
        the_promise: document.getElementById('edit-promise').value,
        funnel_stage: document.getElementById('edit-funnel').value
    };

    try {
        const response = await Auth.fetchWithAuth(`/api/jobs/${currentSOTJobId}/source`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });

        if (!response.ok) throw new Error('Failed to save changes');

        showToast('Source of Truth updated!');

        // Update local data and re-render
        currentSOTData = { ...currentSOTData, ...updates };
        renderSOTModal(currentSOTData, currentSOTData.is_approved);
        toggleSOTEdit();
    } catch (err) {
        console.error('Error saving SOT:', err);
        showToast('Error saving changes');
    }
}

// Close modal on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !document.getElementById('sot-modal').classList.contains('hidden')) {
        closeSOTModal();
    }
});

// Close modal on backdrop click
document.getElementById('sot-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'sot-modal') {
        closeSOTModal();
    }
});
```

**Step 2: Verify JS functions added**

Check that all modal functions are in place.

**Step 3: Commit**

```bash
git add frontend/library.html
git commit -m "feat(library): add SOT modal JavaScript with view/edit functionality"
```

---

## Task 7: Update Library API to Return SOT Info

**Files:**
- Modify: `app/api/library.py` (library endpoint)

**Step 1: Check if library API returns source info**

Read the library API endpoint to see if it returns `source_id` and `source_approved` fields.

**Step 2: If not, update the query**

The library API needs to return `job_id`, `source_id`, and `source_approved` for each entry so the frontend knows:
- Whether to show the SOT button
- Whether the SOT is approved (for styling)

Add a JOIN to the sources table and include these fields in the response.

**Step 3: Test the endpoint**

Verify `/api/library` returns entries with source information.

**Step 4: Commit**

```bash
git add app/api/library.py
git commit -m "feat(api): include SOT info in library entries response"
```

---

## Task 8: Manual Integration Testing

**Step 1: Test Split View Flow**

1. Upload a new file with full pipeline (not quick distill)
2. Wait for Source of Truth approval screen
3. Click "Approve & Continue"
4. Verify split view appears with SOT on left, processing on right
5. Watch processing steps update in real-time
6. Verify "Complete" state appears and reload works

**Step 2: Test Library SOT Modal**

1. Go to Library page
2. Find an entry with SOT (should have "SOT" button)
3. Click SOT button, verify modal opens
4. Verify all fields display correctly
5. Click Edit, modify fields, click Save
6. Verify changes persist

**Step 3: Test Edge Cases**

- Entry without SOT should not show button
- Pending SOT should show amber button
- Approved SOT should show copper button
- Escape key should close modal
- Backdrop click should close modal

---

## Task 9: Final Commit and Push

**Step 1: Verify all changes**

```bash
git status
git diff --stat origin/main
```

**Step 2: Push to remote**

```bash
git push origin main
```

**Step 3: Verify deployment**

Monitor Railway logs to confirm deployment succeeds.
