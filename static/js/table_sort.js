/**
 * table_sort.js — Lightweight vanilla-JS client-side table sorting.
 *
 * Sort cycle: ↕ (none, original order) → ↓ (desc) → ↑ (asc) → ↕ (reset)
 *
 * Works on two kinds of tables:
 *   1. Detail-page tab tables: th[data-sort] + td[data-sort-val], no <a> links in headers.
 *   2. Directory tables: th[data-sort] with <a sort-link> inside them.
 *      - 1st click → client-side desc (no navigation)
 *      - 2nd click → client-side asc  (no navigation)
 *      - 3rd click → navigates to the <a href> to fetch a fresh server-sorted page
 *
 * Usage in templates:
 *   - Add data-sort="text|num" to any <th> you want sortable.
 *   - Add data-sort-val="VALUE" to each <td> in that column.
 *     • For numbers: use the raw integer (or -999999999 sentinel for nulls/suppressed).
 *     • For text:    use the lowercased string.
 *
 * The script re-runs after every HTMX settle so tab fragments work automatically.
 */

(function () {
  'use strict';

  const SORT_ARROW = { none: '↕', asc: '↑', desc: '↓' };
  const NULL_SENTINEL = -999999999; // sorts to bottom on desc, top on asc

  // Cycle: none → desc → asc → none
  const NEXT_DIR = { none: 'desc', desc: 'asc', asc: 'none' };

  function getVal(cell, type) {
    const raw = cell ? (cell.dataset.sortVal ?? '') : '';
    if (type === 'num') {
      const n = parseFloat(raw);
      return isNaN(n) ? NULL_SENTINEL : n;
    }
    return raw.toLowerCase();
  }

  function updateArrows(headers, activeIdx, dir) {
    headers.forEach((th, i) => {
      const span = th.querySelector('.sort-ind, .sort-ind-active');
      if (!span) return;
      if (i === activeIdx && dir !== 'none') {
        span.className = 'sort-ind-active';
        span.textContent = SORT_ARROW[dir];
      } else {
        span.className = 'sort-ind';
        span.textContent = SORT_ARROW.none;
      }
    });
  }

  function initTable(table) {
    if (table._sortInit) return; // already wired up
    table._sortInit = true;

    const headers = Array.from(table.querySelectorAll('thead th[data-sort]'));
    if (!headers.length) return;

    // Snapshot original row order so we can restore it on reset
    const tbody = table.querySelector('tbody');
    const originalOrder = tbody ? Array.from(tbody.querySelectorAll('tr')) : [];

    // Track sort state: which header index (-1 = unsorted) and direction
    const state = { colIdx: -1, dir: 'none' };

    headers.forEach((th, idx) => {
      // Find this header's actual column index in the row
      const allThs = Array.from(th.closest('tr').children);
      const colIdx = allThs.indexOf(th);
      const type = th.dataset.sort || 'text';

      // The inner <a> link (present in directory pages for server-side sort fallback)
      const link = th.querySelector('a');

      // Make it look clickable
      th.style.cursor = 'pointer';

      // Add arrow span if not already present
      if (!th.querySelector('.sort-ind, .sort-ind-active')) {
        const span = document.createElement('span');
        span.className = 'sort-ind';
        span.textContent = SORT_ARROW.none;
        span.style.marginLeft = '4px';
        th.appendChild(span);
      }

      th.addEventListener('click', function (e) {
        if (!tbody) return;

        // Determine next direction
        let newDir;
        if (state.colIdx === idx) {
          newDir = NEXT_DIR[state.dir] || 'desc';
        } else {
          newDir = 'desc';
        }

        // For directory tables: on the reset click, follow the server link instead
        if (newDir === 'none' && link) {
          // Allow the link navigation to happen — let browser follow href
          window.location.href = link.href;
          return;
        }

        // Prevent the inner <a> from navigating during client-side sort clicks
        e.preventDefault();
        e.stopPropagation();

        state.colIdx = idx;
        state.dir = newDir;

        if (newDir === 'none') {
          // Pure client-side reset (no link present) — restore original DOM order
          originalOrder.forEach(r => tbody.appendChild(r));
          headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
          updateArrows(headers, -1, 'none');
        } else {
          const rows = Array.from(tbody.querySelectorAll('tr'));
          rows.sort((a, b) => {
            const cellA = a.children[colIdx];
            const cellB = b.children[colIdx];
            const va = getVal(cellA, type);
            const vb = getVal(cellB, type);

            // Nulls always last regardless of sort direction
            const aIsNull = (type === 'num' && va === NULL_SENTINEL);
            const bIsNull = (type === 'num' && vb === NULL_SENTINEL);
            if (aIsNull && bIsNull) return 0;
            if (aIsNull) return 1;
            if (bIsNull) return -1;

            if (va < vb) return newDir === 'asc' ? -1 : 1;
            if (va > vb) return newDir === 'asc' ? 1 : -1;
            return 0;
          });

          rows.forEach(r => tbody.appendChild(r));

          headers.forEach((h, i) => {
            h.classList.toggle('sort-desc', i === idx && newDir === 'desc');
            h.classList.toggle('sort-asc',  i === idx && newDir === 'asc');
            if (i !== idx) h.classList.remove('sort-asc', 'sort-desc');
          });

          updateArrows(headers, idx, newDir);
        }
      });
    });
  }

  function initAll() {
    document.querySelectorAll('table').forEach(t => {
      if (t.querySelector('thead th[data-sort]')) {
        initTable(t);
      }
    });
  }

  // Initial run
  document.addEventListener('DOMContentLoaded', initAll);

  // Re-run after every HTMX fragment swap (handles tab partials)
  document.addEventListener('htmx:afterSettle', function () {
    document.querySelectorAll('table').forEach(t => {
      if (!t._sortInit && t.querySelector('thead th[data-sort]')) {
        initTable(t);
      }
    });
  });
})();
