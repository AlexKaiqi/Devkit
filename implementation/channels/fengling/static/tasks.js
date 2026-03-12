/**
 * Task Tree UI — Collapsible directory-tree view with SSE real-time updates.
 */

const STATE_COLORS = {
    queued:              '#78909c',
    running:             '#42a5f5',
    completed:           '#66bb6a',
    failed:              '#ef5350',
    waiting_external:    '#ffb74d',
    waiting_user:        '#ffb74d',
    needs_clarification: '#ffb74d',
    needs_confirmation:  '#ffb74d',
    cancelled:           '#616161',
};

const STATE_ICONS = {
    running:             '●',
    completed:           '✓',
    failed:              '✗',
    queued:              '○',
    waiting_external:    '◉',
    waiting_user:        '◉',
    needs_clarification: '◉',
    needs_confirmation:  '◉',
    cancelled:           '○',
};

const TERMINAL_STATES = ['completed', 'failed', 'cancelled'];

// State: task data cache, collapse/detail toggle memory
let taskCache = {};          // taskId -> { task, children }
let collapseState = {};      // taskId -> true (collapsed) / false (expanded)
let detailOpen = {};         // taskId -> true/false
let focusTaskId = null;
let sseSource = null;

// ── Data loading ─────────────────────────────────────

async function loadTasks() {
    try {
        const resp = await fetch('/api/tasks');
        const data = await resp.json();
        const tasks = data.tasks || [];

        const container = document.getElementById('tree-container');
        const emptyState = document.getElementById('empty-state');

        if (tasks.length === 0) {
            container.innerHTML = '';
            emptyState.classList.remove('hidden');
            return;
        }
        emptyState.classList.add('hidden');

        // Update session filter
        const sessions = new Set(tasks.map(t => t.session_key).filter(Boolean));
        updateSessionFilter(sessions);

        // Filter by session if selected
        const sessionFilter = document.getElementById('session-filter').value;
        const filtered = sessionFilter
            ? tasks.filter(t => t.session_key === sessionFilter)
            : tasks;

        // Load full tree data for each root task
        taskCache = {};
        for (const task of filtered) {
            await loadTree(task.task_id);
        }

        // Find focus task (deepest running)
        focusTaskId = findFocusTask(filtered.map(t => t.task_id));

        // Render
        container.innerHTML = '';
        for (const task of filtered) {
            const node = renderTreeNode(task.task_id);
            if (node) container.appendChild(node);
        }
    } catch (err) {
        console.error('Failed to load tasks:', err);
    }
}

async function loadTree(taskId, visited = new Set()) {
    if (visited.has(taskId)) return;
    visited.add(taskId);

    try {
        const resp = await fetch(`/api/tasks/${taskId}`);
        const data = await resp.json();
        if (!data.task) return;

        taskCache[taskId] = { task: data.task, children: data.children || [] };

        for (const child of (data.children || [])) {
            await loadTree(child.task_id, visited);
        }
    } catch (err) {
        console.error(`Failed to load task ${taskId}:`, err);
    }
}

// ── Focus detection ──────────────────────────────────

function findFocusTask(rootIds) {
    let deepest = null;
    let maxDepth = -1;

    function walk(taskId, depth) {
        const cached = taskCache[taskId];
        if (!cached) return;
        const state = cached.task.state;
        if (state === 'running' || state === 'queued') {
            if (depth > maxDepth) {
                maxDepth = depth;
                deepest = taskId;
            }
        }
        for (const child of cached.children) {
            walk(child.task_id, depth + 1);
        }
    }

    for (const rid of rootIds) walk(rid, 0);
    return deepest;
}

function isAncestorOfFocus(taskId) {
    if (!focusTaskId || taskId === focusTaskId) return taskId === focusTaskId;
    // Walk up from focus to see if taskId is ancestor
    function check(tid) {
        const cached = taskCache[tid];
        if (!cached) return false;
        for (const child of cached.children) {
            if (child.task_id === focusTaskId) return true;
            if (check(child.task_id)) return true;
        }
        return false;
    }
    return check(taskId);
}

// ── Default expand logic ─────────────────────────────

function shouldExpand(taskId) {
    // User manually set?
    if (taskId in collapseState) return !collapseState[taskId];

    const cached = taskCache[taskId];
    if (!cached) return false;
    const state = cached.task.state;

    // Focus node and ancestors always expand
    if (taskId === focusTaskId || isAncestorOfFocus(taskId)) return true;

    // Running/queued auto-expand
    if (state === 'running' || state === 'queued') return true;

    // Terminal states default collapsed
    if (TERMINAL_STATES.includes(state)) return false;

    // Waiting states expand
    return true;
}

// ── Rendering ────────────────────────────────────────

function renderTreeNode(taskId) {
    const cached = taskCache[taskId];
    if (!cached) return null;
    const { task, children } = cached;

    const node = document.createElement('div');
    node.className = 'tree-node';
    node.dataset.taskId = taskId;

    const hasChildren = children.length > 0;
    const expanded = hasChildren && shouldExpand(taskId);
    const stateClass = normalizeStateClass(task.state);
    const isFocus = taskId === focusTaskId;

    // Compute child progress
    let progressText = '';
    if (hasChildren) {
        const done = children.filter(c => {
            const cc = taskCache[c.task_id];
            return cc && TERMINAL_STATES.includes(cc.task.state);
        }).length;
        progressText = `${done}/${children.length}`;
    }

    // Task row
    const row = document.createElement('div');
    row.className = 'task-row' + (isFocus ? ' focus' : '');
    row.innerHTML = `
        <span class="toggle-arrow ${hasChildren ? (expanded ? 'expanded' : '') : 'placeholder'}"
              data-task-id="${taskId}">▶</span>
        <span class="status-icon ${stateClass}">${STATE_ICONS[task.state] || '○'}</span>
        <span class="task-title">${escapeHtml(task.title)}</span>
        <span class="state-badge ${stateClass}">${task.state}</span>
        ${progressText ? `<span class="progress-counter">${progressText}</span>` : ''}
        ${isFocus ? '<span class="focus-tag">← 焦点</span>' : ''}
    `;
    node.appendChild(row);

    // Click row → toggle detail
    row.addEventListener('click', (e) => {
        // If clicking toggle arrow, handle expand/collapse instead
        if (e.target.closest('.toggle-arrow') && hasChildren) {
            toggleChildren(taskId);
            return;
        }
        toggleDetail(taskId);
    });

    // Inline detail
    const detail = document.createElement('div');
    detail.className = 'task-detail' + (detailOpen[taskId] ? ' open' : '');
    detail.dataset.detailFor = taskId;
    detail.innerHTML = buildDetailHTML(task, children);
    node.appendChild(detail);

    // Children container
    if (hasChildren) {
        const childContainer = document.createElement('div');
        childContainer.className = 'tree-children' + (expanded ? '' : ' collapsed');
        childContainer.dataset.childrenOf = taskId;
        for (const child of children) {
            const childNode = renderTreeNode(child.task_id);
            if (childNode) childContainer.appendChild(childNode);
        }
        node.appendChild(childContainer);
    }

    return node;
}

function renderMarkdown(text) {
    if (!text) return '';
    try {
        return marked.parse(text, { breaks: true });
    } catch (e) {
        return escapeHtml(text);
    }
}

function buildDetailHTML(task, children) {
    let html = '';

    if (task.intent) {
        html += `<div class="detail-field"><div class="detail-label">意图</div><div class="detail-value markdown-body">${renderMarkdown(task.intent)}</div></div>`;
    }
    if (task.next_action) {
        html += `<div class="detail-field"><div class="detail-label">下一步</div><div class="detail-value markdown-body">${renderMarkdown(task.next_action)}</div></div>`;
    }
    if (task.result_summary) {
        html += `<div class="detail-field"><div class="detail-label">结果</div><div class="detail-value markdown-body">${renderMarkdown(task.result_summary)}</div></div>`;
    }
    if (task.error_summary) {
        html += `<div class="detail-field error"><div class="detail-label">错误</div><div class="detail-value markdown-body">${renderMarkdown(task.error_summary)}</div></div>`;
    }
    if (task.created_at) {
        html += `<div class="detail-field"><div class="detail-label">创建时间</div><div class="detail-value">${formatTime(task.created_at)}</div></div>`;
    }

    // Action buttons
    html += '<div class="detail-actions">';
    if (!TERMINAL_STATES.includes(task.state)) {
        if (task.state !== 'waiting_user') {
            html += `<button onclick="updateTaskState('${task.task_id}', 'waiting_user'); event.stopPropagation();">⏸ 暂停</button>`;
        }
        if (task.state === 'waiting_user') {
            html += `<button onclick="updateTaskState('${task.task_id}', 'running'); event.stopPropagation();">▶ 恢复</button>`;
        }
        html += `<button class="danger" onclick="updateTaskState('${task.task_id}', 'cancelled'); event.stopPropagation();">✕ 取消</button>`;
    }
    html += `<button onclick="promptAddSubtask('${task.task_id}'); event.stopPropagation();">+ 子任务</button>`;
    html += '</div>';

    return html;
}

// ── Interactions ─────────────────────────────────────

function toggleChildren(taskId) {
    const container = document.querySelector(`[data-children-of="${taskId}"]`);
    const arrow = document.querySelector(`.toggle-arrow[data-task-id="${taskId}"]`);
    if (!container) return;

    const isCollapsed = container.classList.contains('collapsed');
    container.classList.toggle('collapsed');
    if (arrow) arrow.classList.toggle('expanded', isCollapsed);

    // Remember user choice
    collapseState[taskId] = !isCollapsed;
}

function toggleDetail(taskId) {
    const detail = document.querySelector(`[data-detail-for="${taskId}"]`);
    if (!detail) return;

    const isOpen = detail.classList.contains('open');
    detail.classList.toggle('open');
    detailOpen[taskId] = !isOpen;
}

// ── Actions ──────────────────────────────────────────

async function updateTaskState(taskId, newState) {
    try {
        await fetch(`/api/tasks/${taskId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ state: newState }),
        });
        await loadTasks();
    } catch (err) {
        console.error('Failed to update task:', err);
    }
}

async function promptAddSubtask(parentId) {
    const title = prompt('子任务标题:');
    if (!title) return;
    const intent = prompt('子任务意图 (可选):') || '';

    try {
        await fetch(`/api/tasks/${parentId}/subtasks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, intent }),
        });
        await loadTasks();
    } catch (err) {
        console.error('Failed to add subtask:', err);
    }
}

// ── SSE ──────────────────────────────────────────────

function connectSSE() {
    if (sseSource) sseSource.close();

    sseSource = new EventSource('/api/tasks/events');

    sseSource.onmessage = (evt) => {
        try {
            const data = JSON.parse(evt.data);
            const taskId = data.task_id;

            // Check if this task exists in our DOM
            const existingNode = document.querySelector(`.tree-node[data-task-id="${taskId}"]`);
            if (existingNode && taskCache[taskId]) {
                // Update cached data
                taskCache[taskId].task.state = data.state;
                if (data.next_action !== undefined) taskCache[taskId].task.next_action = data.next_action;
                if (data.result_summary !== undefined) taskCache[taskId].task.result_summary = data.result_summary;
                if (data.error_summary !== undefined) taskCache[taskId].task.error_summary = data.error_summary;

                // Update DOM in-place
                updateNodeDOM(taskId);
            } else {
                // New task or unknown — reload everything
                loadTasks();
            }
        } catch (err) {
            // ignore parse errors
        }
    };

    sseSource.onerror = () => {
        setTimeout(connectSSE, 5000);
    };
}

function updateNodeDOM(taskId) {
    const cached = taskCache[taskId];
    if (!cached) return;
    const { task, children } = cached;
    const stateClass = normalizeStateClass(task.state);
    const isFocus = taskId === focusTaskId;

    // Update status icon
    const node = document.querySelector(`.tree-node[data-task-id="${taskId}"]`);
    if (!node) return;

    const icon = node.querySelector(':scope > .task-row .status-icon');
    if (icon) {
        icon.className = `status-icon ${stateClass}`;
        icon.textContent = STATE_ICONS[task.state] || '○';
    }

    // Update state badge
    const badge = node.querySelector(':scope > .task-row .state-badge');
    if (badge) {
        badge.className = `state-badge ${stateClass}`;
        badge.textContent = task.state;
    }

    // Update progress
    if (children.length > 0) {
        const counter = node.querySelector(':scope > .task-row .progress-counter');
        const done = children.filter(c => {
            const cc = taskCache[c.task_id];
            return cc && TERMINAL_STATES.includes(cc.task.state);
        }).length;
        if (counter) counter.textContent = `${done}/${children.length}`;
    }

    // Update detail panel if open
    const detail = node.querySelector(':scope > .task-detail');
    if (detail && detail.classList.contains('open')) {
        detail.innerHTML = buildDetailHTML(task, children);
    }
}

// ── Session filter ───────────────────────────────────

function updateSessionFilter(sessions) {
    const select = document.getElementById('session-filter');
    const current = select.value;
    select.innerHTML = '<option value="">所有会话</option>';
    for (const sk of sessions) {
        const opt = document.createElement('option');
        opt.value = sk;
        opt.textContent = sk;
        select.appendChild(opt);
    }
    select.value = current;
}

// ── Helpers ──────────────────────────────────────────

function normalizeStateClass(state) {
    if (state.startsWith('waiting') || state.startsWith('needs')) return 'waiting';
    return state;
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatTime(ts) {
    if (!ts) return '—';
    return new Date(ts * 1000).toLocaleString('zh-CN');
}

// ── Init ─────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    loadTasks();
    connectSSE();

    document.getElementById('btn-refresh').addEventListener('click', () => {
        collapseState = {};
        detailOpen = {};
        loadTasks();
    });
    document.getElementById('session-filter').addEventListener('change', loadTasks);
});
