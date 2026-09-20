    async function loadStats() {
      try {
        const resp = await fetch('/api/stats', {
          headers: getAuthHeaders()
        });
        const data = await resp.json();
        GLOBAL_STATS = data;

        // Creator KPIs
        if (document.getElementById('kpiTotalJobs')) document.getElementById('kpiTotalJobs').textContent = data.total_jobs;
        if (document.getElementById('kpiAvgScore')) document.getElementById('kpiAvgScore').textContent = data.avg_quality_score.toFixed(2);
        if (document.getElementById('kpiTotalAudio')) document.getElementById('kpiTotalAudio').textContent = data.total_audio_minutes;
        if (document.getElementById('kpiTotalCost')) document.getElementById('kpiTotalCost').textContent = `$${data.total_cost_usd.toFixed(4)}`;
        if (document.getElementById('kpiDbBackend')) document.getElementById('kpiDbBackend').textContent = data.gcp_environment.repository_type.replace('JobRepository', '');
        if (document.getElementById('navProjectId')) document.getElementById('navProjectId').textContent = data.gcp_environment.project_id;

        // Auditor KPIs
        if (document.getElementById('kpiPassRate')) document.getElementById('kpiPassRate').textContent = `${(data.pass_rate !== undefined ? data.pass_rate : 100).toFixed(1)}%`;
        if (document.getElementById('kpiAuditedDisclosures')) document.getElementById('kpiAuditedDisclosures').textContent = data.audited_count ?? data.total_jobs;
        if (document.getElementById('kpiFlaggedItems')) document.getElementById('kpiFlaggedItems').textContent = data.flagged_count ?? 0;
        if (document.getElementById('kpiAuditorCost')) document.getElementById('kpiAuditorCost').textContent = `$${data.total_cost_usd.toFixed(4)}`;

        // Full-Page Auditor Dashboard & Charts
        if (CURRENT_PERSONA === 'auditor') {
          renderAuditorDashboard(data);
          renderAuditorCharts(data);
        }
      } catch (err) {
        console.error('Error fetching stats:', err);
      }
    }

    let POLLING_INTERVAL = null;

    // Jobs Directory
    async function loadJobs() {
      const tbody = document.getElementById('jobsTableBody');
      try {
        const resp = await fetch('/api/jobs?limit=500', {
          headers: getAuthHeaders()
        });
        ALL_JOBS = await resp.json();
        const badge = document.getElementById('auditorJobCountBadge');
        if (badge) badge.textContent = ALL_JOBS.length;
        filterJobs(true);
        checkAndStartPolling();
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" class="px-5 py-6 text-center text-rose-400">Failed to load jobs: ${err.message}</td></tr>`;
      }
    }

    async function loadJobsSilently() {
      try {
        const resp = await fetch('/api/jobs?limit=500', {
          headers: getAuthHeaders()
        });
        if (resp.ok) {
          ALL_JOBS = await resp.json();
          filterJobs(false);
          checkAndStartPolling();
        }
      } catch (err) {
        console.error('Silent jobs polling error:', err);
      }
    }

    function checkAndStartPolling() {
      const hasRunning = ALL_JOBS.some(j => j.status === 'RUNNING');
      if (hasRunning && !POLLING_INTERVAL) {
        POLLING_INTERVAL = setInterval(async () => {
          await loadStats();
          await loadJobsSilently();

          // Auto-refresh detail modal ONLY if user currently has the drawer open
          const modalEl = document.getElementById('jobDetailModal');
          const isModalOpen = modalEl && !modalEl.classList.contains('hidden');
          if (isModalOpen && CURRENT_JOB && CURRENT_JOB.status === 'RUNNING') {
            const updated = ALL_JOBS.find(j => j.job_id === CURRENT_JOB.job_id);
            if (updated) {
              openJobDetail(updated.job_id);
            }
          }
        }, 3000);
      } else if (!hasRunning && POLLING_INTERVAL) {
        clearInterval(POLLING_INTERVAL);
        POLLING_INTERVAL = null;
      }
    }

    function filterJobs(resetPage = true) {
      const persona = document.getElementById('personaFilter').value;
      let list = [...ALL_JOBS];

      if (persona !== 'All') {
        list = list.filter(j => j.persona === persona);
      }

      if (CURRENT_PERSONA === 'auditor' && COMPLIANCE_FILTER !== 'all') {
        if (COMPLIANCE_FILTER === 'compliant') {
          list = list.filter(j => j.overall_score !== null && j.overall_score !== undefined && j.overall_score >= 4.0);
        } else if (COMPLIANCE_FILTER === 'flagged') {
          list = list.filter(j => j.status === 'FAILED' || (j.overall_score !== null && j.overall_score !== undefined && j.overall_score < 4.0));
        }
      }

      FILTERED_JOBS = list;
      if (resetPage) {
        CURRENT_PAGE = 1;
      }
      updatePaginationAndRender();
    }

    function renderJobs(jobs) {
      const tbody = document.getElementById('jobsTableBody');
      if (!jobs || jobs.length === 0) {
        const emptyMsg = CURRENT_PERSONA === 'auditor'
          ? 'No audited disclosures matching the selected compliance filter.'
          : 'No voice synthesis jobs found. Click "+ New Voice Synthesis" to create one.';
        tbody.innerHTML = `<tr><td colspan="8" class="px-5 py-8 text-center text-zinc-500">${emptyMsg}</td></tr>`;
        return;
      }

      tbody.innerHTML = jobs.map(j => {
        const timeStr = new Date(j.created_at).toLocaleString();
        
        let scoreBadge = '';
        if (j.status === 'RUNNING') {
          scoreBadge = `<span class="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20 inline-flex items-center space-x-1.5"><i data-lucide="loader-2" class="w-3 h-3 animate-spin"></i><span>Synthesizing...</span></span>`;
        } else if (j.status === 'FAILED') {
          scoreBadge = `<span class="px-2 py-0.5 rounded text-xs font-mono font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">FAILED</span>`;
        } else if (j.overall_score !== null && j.overall_score !== undefined) {
          scoreBadge = `<span class="px-2 py-0.5 rounded text-xs font-mono font-bold ${j.overall_score >= 4.0 ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'}">★ ${j.overall_score.toFixed(1)} / 5.0</span>`;
        } else {
          scoreBadge = `<span class="text-zinc-500 font-mono text-xs">Audit Pending</span>`;
        }
        
        const audienceColor = j.audience.includes('External') ? 'text-amber-400' : (j.audience.includes('Internal') ? 'text-blue-400' : 'text-purple-400');
        const prefixKey = j.audience.includes('External') ? 'external/audio/' : (j.audience.includes('Internal') ? 'internal/audio/' : 'shared/audio/');
        const costStr = j.cost ? `$${j.cost.total_cost_usd.toFixed(4)}` : '$0.0000';

        let actionBtn = '';
        if (j.status === 'RUNNING') {
          actionBtn = `
            <button onclick="openJobDetail('${j.job_id}')"
              class="px-3 py-1.5 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded-lg text-xs font-medium transition flex items-center space-x-1.5 ml-auto animate-pulse">
              <i data-lucide="activity" class="w-3.5 h-3.5"></i>
              <span>Track Live</span>
            </button>
          `;
        } else if (j.status === 'FAILED') {
          actionBtn = `
            <button onclick="openJobDetail('${j.job_id}')"
              class="px-3 py-1.5 bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 border border-rose-800/40 rounded-lg text-xs font-medium transition flex items-center space-x-1 ml-auto">
              <i data-lucide="alert-circle" class="w-3.5 h-3.5"></i>
              <span>Error Details</span>
            </button>
          `;
        } else if (CURRENT_PERSONA === 'auditor') {
          actionBtn = `
            <button onclick="openJobDetail('${j.job_id}')"
              class="px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600/40 text-purple-200 border border-purple-500/30 rounded-lg text-xs font-semibold transition flex items-center space-x-1.5 ml-auto shadow-sm">
              <i data-lucide="shield-check" class="w-3.5 h-3.5 text-purple-300"></i>
              <span>Audit Scorecard</span>
            </button>
          `;
        } else {
          actionBtn = `
            <button onclick="openJobDetail('${j.job_id}')"
              class="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg text-xs font-medium transition flex items-center space-x-1 ml-auto">
              <i data-lucide="eye" class="w-3.5 h-3.5"></i>
              <span>Details</span>
            </button>
          `;
        }

        const rowClick = `onclick="openJobDetail('${j.job_id}')"`;
        const cursorStyle = 'cursor-pointer hover:bg-zinc-800/40';

        let durationDisplay = '--';
        const speedPill = (j.speed && Math.abs(j.speed - 1.0) >= 0.04)
          ? `<span class="ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-zinc-800 text-zinc-300 border border-zinc-700 inline-block align-middle" title="Generated Delivery Speed">${Number(j.speed).toFixed(2)}x</span>`
          : '';
        if (j.duration_seconds) {
          durationDisplay = `<span class="align-middle">${j.duration_seconds.toFixed(1)}s</span>${speedPill}`;
        } else if (j.status === 'RUNNING') {
          if (j.current_turn && j.total_turns && j.total_turns > 1) {
            durationDisplay = `<span class="animate-pulse text-amber-400 font-mono text-[11px] align-middle">turn ${j.current_turn}/${j.total_turns}</span>${speedPill}`;
          } else {
            const stageLabel = (j.progress_stage || 'synthesizing').toLowerCase();
            durationDisplay = `<span class="animate-pulse text-amber-400 font-mono text-[11px] align-middle">${stageLabel}</span>${speedPill}`;
          }
        }

        const showAdminActions = CURRENT_PERSONA !== 'auditor';

        return `
          <tr class="${cursorStyle} transition" ${rowClick}>
            <td class="px-5 py-4 whitespace-nowrap">
              <div class="font-mono font-bold text-white text-xs flex items-center space-x-1">
                <span>${j.job_id}</span>
                ${j.retry_count && j.retry_count > 0 ? `<span class="px-1.5 py-0.2 rounded text-[9px] font-mono bg-cyan-500/20 text-cyan-300 border border-cyan-500/30" title="Take ${j.retry_count + 1} (Critic-Steered)">Take ${j.retry_count + 1}</span>` : ''}
              </div>
              <div class="text-[11px] text-zinc-500">${timeStr}</div>
            </td>
            <td class="px-5 py-4">
              <div class="font-medium text-zinc-200 max-w-xs truncate flex items-center space-x-1.5">
                ${j.source_url ? `<i data-lucide="globe" class="w-3.5 h-3.5 text-teal-400 shrink-0" title="Source: ${j.source_url}"></i>` : ''}
                <span class="truncate">${j.article_title || 'Financial Article'}</span>
              </div>
              <div class="text-[11px] text-zinc-500 font-mono">${j.word_count} words • ${j.char_count} chars</div>
            </td>
            <td class="px-5 py-4 whitespace-nowrap">
              <div class="text-zinc-200 font-medium">${j.persona}</div>
              <div class="text-[11px] text-zinc-500">Voice: <span class="text-emerald-400 font-mono">${j.voice_name}</span></div>
            </td>
            <td class="px-5 py-4 whitespace-nowrap">
              <div class="text-xs font-medium ${audienceColor}">${j.audience}</div>
              <div class="text-[10px] text-zinc-500 font-mono">${prefixKey}</div>
            </td>
            <td class="px-5 py-4 whitespace-nowrap font-mono text-zinc-300">
              ${durationDisplay}
            </td>
            <td class="px-5 py-4 whitespace-nowrap">
              ${scoreBadge}
              ${j.previous_attempt_score && j.overall_score ? `
                <div class="text-[10px] font-mono mt-0.5 ${(j.overall_score - j.previous_attempt_score) >= 0 ? 'text-emerald-400' : 'text-rose-400'}" title="Score vs previous take">
                  ${(j.overall_score - j.previous_attempt_score) >= 0 ? '+' : ''}${(j.overall_score - j.previous_attempt_score).toFixed(1)} vs Take 1
                </div>` : ''}
            </td>
            <td class="px-5 py-4 whitespace-nowrap font-mono text-emerald-400 font-semibold">
              ${costStr}
            </td>
            <td class="px-5 py-4 whitespace-nowrap text-right" onclick="event.stopPropagation()">
              <div class="flex items-center justify-end space-x-1.5">
                ${showAdminActions ? `
                <button onclick="openRetryModal('${j.job_id}', event)" title="Retry Voice Synthesis with Auditor Feedback"
                  class="p-1.5 bg-zinc-800/80 hover:bg-cyan-950/60 text-zinc-400 hover:text-cyan-400 border border-zinc-700/60 hover:border-cyan-800/60 rounded-lg transition flex items-center justify-center">
                  <i data-lucide="rotate-cw" class="w-3.5 h-3.5"></i>
                </button>` : ''}
                ${actionBtn}
                ${showAdminActions ? `
                <button onclick="deleteJob('${j.job_id}', event)" title="Delete Job"
                  class="p-1.5 bg-zinc-800/80 hover:bg-rose-950/60 text-zinc-400 hover:text-rose-400 border border-zinc-700/60 hover:border-rose-800/60 rounded-lg transition flex items-center justify-center">
                  <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                </button>` : ''}
              </div>
            </td>
          </tr>
        `;
      }).join('');

      lucide.createIcons();
    }

    // Pagination Handlers
    function changePageSize(newSize) {
      PAGE_SIZE = parseInt(newSize, 10) || 10;
      CURRENT_PAGE = 1;
      updatePaginationAndRender();
    }

    function goToPage(page) {
      const totalPages = Math.max(1, Math.ceil(FILTERED_JOBS.length / PAGE_SIZE));
      if (page < 1) page = 1;
      if (page > totalPages) page = totalPages;
      CURRENT_PAGE = page;
      updatePaginationAndRender();
    }

    function goToLastPage() {
      const totalPages = Math.max(1, Math.ceil(FILTERED_JOBS.length / PAGE_SIZE));
      goToPage(totalPages);
    }

    function updatePaginationAndRender() {
      const totalItems = FILTERED_JOBS.length;
      const totalPages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE));
      if (CURRENT_PAGE > totalPages) CURRENT_PAGE = totalPages;
      if (CURRENT_PAGE < 1) CURRENT_PAGE = 1;

      const startIdx = totalItems === 0 ? 0 : (CURRENT_PAGE - 1) * PAGE_SIZE;
      const endIdx = totalItems === 0 ? 0 : Math.min(startIdx + PAGE_SIZE, totalItems);
      const pagedJobs = totalItems > 0 ? FILTERED_JOBS.slice(startIdx, endIdx) : [];

      renderJobs(pagedJobs);
      renderPaginationUI(totalItems, totalPages, startIdx, endIdx);
    }

    function renderPaginationUI(totalItems, totalPages, startIdx, endIdx) {
      const rangeStartEl = document.getElementById('paginationRangeStart');
      const rangeEndEl = document.getElementById('paginationRangeEnd');
      const totalItemsEl = document.getElementById('paginationTotalItems');
      const btnFirst = document.getElementById('btnFirstPage');
      const btnPrev = document.getElementById('btnPrevPage');
      const btnNext = document.getElementById('btnNextPage');
      const btnLast = document.getElementById('btnLastPage');
      const pageNumbersContainer = document.getElementById('pageNumberButtons');

      if (rangeStartEl) rangeStartEl.textContent = totalItems === 0 ? '0' : (startIdx + 1);
      if (rangeEndEl) rangeEndEl.textContent = endIdx;
      if (totalItemsEl) totalItemsEl.textContent = totalItems;

      const isFirst = CURRENT_PAGE <= 1;
      const isLast = CURRENT_PAGE >= totalPages || totalItems === 0;

      if (btnFirst) btnFirst.disabled = isFirst;
      if (btnPrev) btnPrev.disabled = isFirst;
      if (btnNext) btnNext.disabled = isLast;
      if (btnLast) btnLast.disabled = isLast;

      if (!pageNumbersContainer) return;

      // Smart page numbering
      let pages = [];
      if (totalPages <= 5) {
        for (let i = 1; i <= totalPages; i++) pages.push(i);
      } else {
        if (CURRENT_PAGE <= 3) {
          pages = [1, 2, 3, 4, '...', totalPages];
        } else if (CURRENT_PAGE >= totalPages - 2) {
          pages = [1, '...', totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
        } else {
          pages = [1, '...', CURRENT_PAGE - 1, CURRENT_PAGE, CURRENT_PAGE + 1, '...', totalPages];
        }
      }

      pageNumbersContainer.innerHTML = pages.map(p => {
        if (p === '...') {
          return `<span class="px-1 text-zinc-600 select-none">…</span>`;
        }
        const isActive = p === CURRENT_PAGE;
        if (isActive) {
          return `<button class="w-7 h-7 rounded-lg bg-emerald-500 text-zinc-950 font-bold font-mono text-xs flex items-center justify-center shadow-sm" aria-current="page">${p}</button>`;
        }
        return `<button onclick="goToPage(${p})" class="w-7 h-7 rounded-lg border border-zinc-800 bg-zinc-900 text-zinc-400 hover:text-white hover:bg-zinc-800 font-mono text-xs flex items-center justify-center transition">${p}</button>`;
      }).join('');

      lucide.createIcons();
    }

    // Job Detail Modal Handlers
