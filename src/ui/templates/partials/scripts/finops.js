    // ================= FINOPS & COMPLIANCE GOVERNANCE DRAWER =================
    async function openFinOpsDrawer() {
      if (CURRENT_PERSONA !== 'auditor') {
        await selectPersona('auditor');
      }
      switchAuditorSubView('dashboard');
      const drawer = document.getElementById('finOpsDrawer');
      if (drawer) {
        drawer.classList.remove('hidden');
        document.body.classList.add('overflow-hidden');
        await refreshFinOpsData();
        lucide.createIcons();
      }
    }

    function closeFinOpsDrawer() {
      const drawer = document.getElementById('finOpsDrawer');
      if (!drawer) return;
      drawer.classList.add('hidden');
      document.body.classList.remove('overflow-hidden');
    }

    async function refreshFinOpsData() {
      const refreshIcon = document.getElementById('foRefreshIcon');
      if (refreshIcon) refreshIcon.classList.add('animate-spin');
      try {
        const resp = await fetch('/api/stats', { headers: getAuthHeaders() });
        if (!resp.ok) return;
        const stats = await resp.json();
        renderFinOpsDrawer(stats);
      } catch (err) {
        console.error('Failed to fetch FinOps stats', err);
      } finally {
        if (refreshIcon) {
          setTimeout(() => refreshIcon.classList.remove('animate-spin'), 300);
        }
      }
    }

    function renderFinOpsDrawer(stats) {
      if (!stats) return;

      // 1. Top-line KPIs
      const costEl = document.getElementById('foTotalCost');
      if (costEl) costEl.textContent = `$${(stats.total_cost_usd || 0).toFixed(4)}`;

      const ttsSplitEl = document.getElementById('foTtsCostSplit');
      if (ttsSplitEl && stats.cost_breakdown) {
        ttsSplitEl.textContent = `TTS: $${(stats.cost_breakdown.tts_cost_usd || 0).toFixed(4)} | Judge: $${(stats.cost_breakdown.judge_cost_usd || 0).toFixed(4)}`;
      }

      const tokensEl = document.getElementById('foTotalTokens');
      if (tokensEl) tokensEl.textContent = (stats.total_tokens || 0).toLocaleString();

      const tokenBreakdownEl = document.getElementById('foTokenBreakdown');
      if (tokenBreakdownEl && stats.token_breakdown) {
        const tb = stats.token_breakdown;
        tokenBreakdownEl.textContent = `Text: ${(tb.input_text_tokens || 0).toLocaleString()} | Audio: ${(tb.audio_output_tokens || 0).toLocaleString()} | Judge: ${((tb.judge_input_tokens || 0) + (tb.judge_output_tokens || 0)).toLocaleString()}`;
      }

      const passRateEl = document.getElementById('foPassRate');
      if (passRateEl) passRateEl.textContent = `${stats.pass_rate || 0}%`;

      const passCountsEl = document.getElementById('foPassCounts');
      if (passCountsEl) passCountsEl.textContent = `${stats.compliant_count || 0} Pass / ${stats.flagged_count || 0} Flagged`;

      const minutesEl = document.getElementById('foTotalMinutes');
      if (minutesEl) minutesEl.textContent = `${stats.total_audio_minutes || 0} min`;

      const totalJobsEl = document.getElementById('foTotalJobs');
      if (totalJobsEl) totalJobsEl.textContent = `Across ${stats.total_jobs || 0} Total Disclosures`;

      const avgScoreEl = document.getElementById('foAvgScore');
      if (avgScoreEl) avgScoreEl.textContent = stats.avg_quality_score ? `${stats.avg_quality_score} / 5.0` : '--';

      // 2. Multimodal Rubric Dimensions
      const rubricContainer = document.getElementById('foRubricDimensionList');
      if (rubricContainer && stats.rubric_averages) {
        rubricContainer.innerHTML = Object.entries(stats.rubric_averages).map(([key, dim]) => {
          const score = dim.avg_score || 0;
          const pct = Math.min(Math.max((score / 5.0) * 100, 0), 100);
          const isCompliant = score >= 4.0;
          const barColor = isCompliant ? 'from-emerald-500 to-teal-400' : 'from-amber-500 to-rose-500';
          const badgeClass = isCompliant 
            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' 
            : 'bg-amber-500/10 text-amber-400 border-amber-500/20';

          return `
            <div class="p-3 bg-zinc-900 border border-zinc-800/80 rounded-xl space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-xs font-medium text-zinc-200">${dim.label}</span>
                <span class="px-2 py-0.5 rounded text-[10px] font-semibold border ${badgeClass}">
                  ${score.toFixed(2)} / 5.0
                </span>
              </div>
              <div class="w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                <div class="h-1.5 rounded-full bg-gradient-to-r ${barColor}" style="width: ${pct}%"></div>
              </div>
              <div class="flex items-center justify-between text-[10px] text-zinc-400">
                <span>${dim.count} Audited</span>
                <span class="${isCompliant ? 'text-emerald-400' : 'text-amber-400'} font-medium">
                  ${isCompliant ? '✓ Compliant' : '⚠ Review Required'}
                </span>
              </div>
            </div>
          `;
        }).join('');
      }

      // 3. Persona Matrix Table
      const personaTbody = document.getElementById('foPersonaTableBody');
      if (personaTbody && stats.persona_matrix) {
        personaTbody.innerHTML = Object.entries(stats.persona_matrix).map(([name, p]) => {
          const isCompliant = p.status === 'COMPLIANT';
          const badgeClass = isCompliant 
            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' 
            : 'bg-amber-500/10 text-amber-400 border-amber-500/20';
          const scoreText = p.avg_score ? p.avg_score.toFixed(2) : '--';

          return `
            <tr class="hover:bg-zinc-800/30 transition">
              <td class="py-2.5 px-3 font-medium text-white flex items-center space-x-2">
                <span class="w-2 h-2 rounded-full ${isCompliant ? 'bg-emerald-400' : 'bg-amber-400'}"></span>
                <span>${name}</span>
              </td>
              <td class="py-2.5 px-3 text-center font-mono">${p.total_jobs}</td>
              <td class="py-2.5 px-3 text-center font-mono ${p.pass_rate >= 80 ? 'text-emerald-400' : 'text-amber-400'}">${p.pass_rate}%</td>
              <td class="py-2.5 px-3 text-center font-mono text-zinc-200">${scoreText}</td>
              <td class="py-2.5 px-3 text-right font-mono text-purple-300">$${(p.total_cost_usd || 0).toFixed(4)}</td>
              <td class="py-2.5 px-3 text-center">
                <span class="px-2 py-0.5 rounded text-[10px] font-semibold border ${badgeClass}">
                  ${isCompliant ? 'Compliant' : 'Needs Attention'}
                </span>
              </td>
            </tr>
          `;
        }).join('');
      }

      // 4. Unit Economics
      const costPerMinEl = document.getElementById('foCostPerMin');
      if (costPerMinEl && stats.unit_economics) {
        costPerMinEl.textContent = `$${stats.unit_economics.cost_per_audio_minute.toFixed(4)} / min`;
      }

      const costPerJobEl = document.getElementById('foCostPerJob');
      if (costPerJobEl && stats.unit_economics) {
        costPerJobEl.textContent = `$${stats.unit_economics.cost_per_job.toFixed(4)} / asset`;
      }

      const judgeRatioEl = document.getElementById('foJudgeCostRatio');
      if (judgeRatioEl && stats.cost_breakdown) {
        judgeRatioEl.textContent = `${stats.cost_breakdown.judge_cost_percentage}% of total spend`;
      }

      const backendRepoEl = document.getElementById('foBackendRepo');
      if (backendRepoEl && stats.gcp_environment) {
        backendRepoEl.textContent = stats.gcp_environment.repository_type === 'FirestoreJobRepository' 
          ? 'Firestore Native (tts-jobs)' 
          : 'InMemory (Local Test Mode)';
      }

      const bucketNameEl = document.getElementById('foBucketName');
      if (bucketNameEl && stats.gcp_environment) {
        bucketNameEl.textContent = stats.gcp_environment.bucket_name || 'knowledge-to-audio-poc';
      }

      // 5. Flagged Disclosures List
      const flaggedCountHeader = document.getElementById('foFlaggedHeaderCount');
      if (flaggedCountHeader) {
        const count = stats.flagged_jobs ? stats.flagged_jobs.length : 0;
        flaggedCountHeader.textContent = `${count} Flagged`;
        if (count === 0) {
          flaggedCountHeader.className = 'text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-medium';
        } else {
          flaggedCountHeader.className = 'text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 font-medium';
        }
      }

      const flaggedContainer = document.getElementById('foFlaggedContainer');
      if (flaggedContainer) {
        if (!stats.flagged_jobs || stats.flagged_jobs.length === 0) {
          flaggedContainer.innerHTML = `
            <div class="p-4 bg-emerald-950/20 border border-emerald-500/20 rounded-xl text-center">
              <i data-lucide="check-circle-2" class="w-5 h-5 text-emerald-400 mx-auto mb-1"></i>
              <p class="text-xs text-emerald-300 font-medium">All audio assets meet regulatory quality requirements (&ge; 4.0 / 5.0).</p>
            </div>
          `;
        } else {
          flaggedContainer.innerHTML = stats.flagged_jobs.map(j => `
            <div class="p-3 bg-zinc-900 border border-amber-800/40 rounded-xl flex items-center justify-between gap-3 hover:border-amber-700/60 transition">
              <div class="space-y-1 min-w-0">
                <div class="flex items-center space-x-2">
                  <span class="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-bold font-mono">
                    ${j.overall_score.toFixed(2)} / 5.0
                  </span>
                  <span class="text-xs font-semibold text-white truncate max-w-[280px]">${j.title}</span>
                  <span class="text-[10px] text-zinc-400 font-medium">${j.persona}</span>
                </div>
                <p class="text-[11px] text-zinc-400 line-clamp-1">${j.overall_reasoning}</p>
              </div>
              <button onclick="closeFinOpsDrawer(); openJobDetail('${j.job_id}');"
                class="shrink-0 px-2.5 py-1.5 bg-purple-600/30 hover:bg-purple-600/50 border border-purple-500/40 text-purple-200 text-xs font-semibold rounded-lg transition flex items-center space-x-1 shadow-sm">
                <i data-lucide="shield" class="w-3.5 h-3.5 text-purple-300"></i>
                <span>Audit</span>
              </button>
            </div>
          `).join('');
        }
      }

      lucide.createIcons();
    }

