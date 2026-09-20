    // ================= FULL-PAGE AUDITOR GOVERNANCE DASHBOARD =================
    function switchAuditorSubView(subview) {
      AUDITOR_SUB_VIEW = subview;
      const btnDashboard = document.getElementById('btnAuditorSubDashboard');
      const btnRegistry = document.getElementById('btnAuditorSubRegistry');
      const fullDashboard = document.getElementById('auditorFullDashboard');
      const jobRegistry = document.getElementById('jobDirectorySection');

      const activeCls = 'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center space-x-2 bg-purple-600/30 text-purple-200 border border-purple-500/40 shadow-sm';
      const inactiveCls = 'px-4 py-2 rounded-xl text-xs font-semibold text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60 border border-transparent transition flex items-center space-x-2';

      if (subview === 'dashboard') {
        if (btnDashboard) btnDashboard.className = activeCls;
        if (btnRegistry) btnRegistry.className = inactiveCls;
        if (fullDashboard) fullDashboard.classList.remove('hidden');
        if (jobRegistry) jobRegistry.classList.add('hidden');
        if (GLOBAL_STATS) {
          renderAuditorDashboard(GLOBAL_STATS);
          setTimeout(() => renderAuditorCharts(GLOBAL_STATS), 60);
        }
      } else {
        if (btnDashboard) btnDashboard.className = inactiveCls;
        if (btnRegistry) btnRegistry.className = activeCls;
        if (fullDashboard) fullDashboard.classList.add('hidden');
        if (jobRegistry) jobRegistry.classList.remove('hidden');
      }
      lucide.createIcons();
    }

    async function refreshAuditorDashboard() {
      const icon = document.getElementById('auditorRefreshIcon');
      if (icon) icon.classList.add('animate-spin');
      try {
        await loadStats();
        await loadJobs();
        if (AUDITOR_SUB_VIEW === 'dashboard' && GLOBAL_STATS) {
          renderAuditorDashboard(GLOBAL_STATS);
          renderAuditorCharts(GLOBAL_STATS);
        }
      } catch (err) {
        console.error('Failed to refresh auditor dashboard:', err);
      } finally {
        if (icon) {
          setTimeout(() => icon.classList.remove('animate-spin'), 300);
        }
      }
    }

    function renderAuditorDashboard(stats) {
      if (!stats) return;

      // 1. Top-line KPIs
      const costEl = document.getElementById('fullFoTotalCost');
      if (costEl) costEl.textContent = `$${(stats.total_cost_usd || 0).toFixed(4)}`;

      const ttsSplitEl = document.getElementById('fullFoTtsSplit');
      if (ttsSplitEl && stats.cost_breakdown) {
        ttsSplitEl.textContent = `TTS: $${(stats.cost_breakdown.tts_cost_usd || 0).toFixed(4)} | Judge: $${(stats.cost_breakdown.judge_cost_usd || 0).toFixed(4)}`;
      }

      const tokensEl = document.getElementById('fullFoTotalTokens');
      if (tokensEl) tokensEl.textContent = (stats.total_tokens || 0).toLocaleString();

      const tokenSplitEl = document.getElementById('fullFoTokenSplit');
      if (tokenSplitEl && stats.token_breakdown) {
        const tb = stats.token_breakdown;
        tokenSplitEl.textContent = `Text: ${(tb.input_text_tokens || 0).toLocaleString()} | Audio: ${(tb.audio_output_tokens || 0).toLocaleString()} | Judge: ${((tb.judge_input_tokens || 0) + (tb.judge_output_tokens || 0)).toLocaleString()}`;
      }

      const passRateEl = document.getElementById('fullFoPassRate');
      if (passRateEl) passRateEl.textContent = `${(stats.pass_rate !== undefined ? stats.pass_rate : 100).toFixed(1)}%`;

      const passCountsEl = document.getElementById('fullFoPassCounts');
      if (passCountsEl) passCountsEl.textContent = `${stats.compliant_count || 0} Compliant / ${stats.flagged_count || 0} Needs Review`;

      const minutesEl = document.getElementById('fullFoTotalMinutes');
      if (minutesEl) minutesEl.textContent = `${(stats.total_audio_minutes || 0).toFixed(1)} min`;

      const avgScoreEl = document.getElementById('fullFoAvgScore');
      if (avgScoreEl) avgScoreEl.textContent = stats.avg_quality_score ? `${stats.avg_quality_score.toFixed(2)} / 5.0` : '--';

      // 2. Foundation Model Telemetry & FinOps Matrix Table
      const modelTbody = document.getElementById('fullFoModelTableBody');
      const modelTfoot = document.getElementById('fullFoModelTableFoot');
      const modelActiveEl = document.getElementById('modelMatrixActiveCount');
      const modelSpendEl = document.getElementById('modelMatrixFleetSpend');

      if (stats.model_matrix && modelTbody) {
        const models = Object.values(stats.model_matrix);
        if (modelActiveEl) modelActiveEl.textContent = `${models.length} Active`;
        if (modelSpendEl) modelSpendEl.textContent = `$${(stats.total_cost_usd || 0).toFixed(4)}`;

        modelTbody.innerHTML = models.map(m => {
          const isTts = m.role.toLowerCase().includes('speech') || m.role.toLowerCase().includes('tts');
          const badgeColor = isTts
            ? 'bg-cyan-500/10 text-cyan-300 border-cyan-500/20'
            : 'bg-purple-500/10 text-purple-300 border-purple-500/20';
          const iconName = isTts ? 'mic' : 'shield-check';

          return `
            <tr class="hover:bg-zinc-800/40 transition">
              <td class="py-3 px-4">
                <div class="flex items-center space-x-2.5">
                  <span class="p-1.5 rounded-lg ${badgeColor} border">
                    <i data-lucide="${iconName}" class="w-3.5 h-3.5"></i>
                  </span>
                  <div>
                    <div class="font-bold text-white text-xs font-mono">${m.model}</div>
                    <div class="text-[11px] text-zinc-400">${m.display_name || m.role}</div>
                  </div>
                </div>
              </td>
              <td class="py-3 px-4">
                <div class="text-xs text-zinc-200 font-medium">${m.role}</div>
                <div class="text-[10px] text-zinc-400 font-mono">${m.modality}</div>
              </td>
              <td class="py-3 px-4 text-right">
                <div class="font-mono text-cyan-300 font-bold">${(m.input_tokens || 0).toLocaleString()}</div>
                <div class="text-[10px] text-zinc-500 font-mono">${m.input_pricing}</div>
              </td>
              <td class="py-3 px-4 text-right">
                <div class="font-mono text-purple-300 font-bold">${(m.output_tokens || 0).toLocaleString()}</div>
                <div class="text-[10px] text-zinc-500 font-mono">${m.output_pricing}</div>
              </td>
              <td class="py-3 px-4 text-right">
                <div class="font-mono text-white font-bold">${(m.total_tokens || 0).toLocaleString()}</div>
                <div class="text-[10px] text-zinc-400 font-mono">${m.token_percentage}% fleet</div>
              </td>
              <td class="py-3 px-4 text-right">
                <div class="font-mono text-emerald-400 font-bold">$${(m.total_cost_usd || 0).toFixed(4)}</div>
                <div class="text-[10px] text-zinc-500 font-mono">${m.job_count} runs</div>
              </td>
              <td class="py-3 px-4 text-center">
                <div class="flex flex-col items-center gap-1">
                  <span class="px-2 py-0.5 rounded text-[10px] font-bold font-mono ${isTts ? 'bg-cyan-500/10 text-cyan-300 border border-cyan-500/30' : 'bg-purple-500/10 text-purple-300 border border-purple-500/30'}">
                    ${m.cost_percentage}%
                  </span>
                  <div class="w-16 bg-zinc-800 rounded-full h-1 overflow-hidden">
                    <div class="${isTts ? 'bg-cyan-400' : 'bg-purple-400'} h-1 rounded-full" style="width: ${Math.min(100, m.cost_percentage)}%"></div>
                  </div>
                </div>
              </td>
            </tr>
          `;
        }).join('');

        if (modelTfoot) {
          const totalIn = models.reduce((acc, m) => acc + (m.input_tokens || 0), 0);
          const totalOut = models.reduce((acc, m) => acc + (m.output_tokens || 0), 0);
          const totalTokens = totalIn + totalOut;
          const totalCost = models.reduce((acc, m) => acc + (m.total_cost_usd || 0), 0);

          modelTfoot.innerHTML = `
            <tr>
              <td class="py-3 px-4 font-bold text-white uppercase text-[10px] tracking-wider" colspan="2">Fleet Combined Totals</td>
              <td class="py-3 px-4 text-right text-cyan-300 font-bold">${totalIn.toLocaleString()} in</td>
              <td class="py-3 px-4 text-right text-purple-300 font-bold">${totalOut.toLocaleString()} out</td>
              <td class="py-3 px-4 text-right text-white font-bold">${totalTokens.toLocaleString()}</td>
              <td class="py-3 px-4 text-right text-emerald-400 font-bold">$${totalCost.toFixed(4)}</td>
              <td class="py-3 px-4 text-center text-zinc-400 font-bold">100.0%</td>
            </tr>
          `;
        }
      }

      // 3. Persona Governance Matrix Table
      const personaTbody = document.getElementById('fullFoPersonaTableBody');
      if (personaTbody && stats.persona_matrix) {
        personaTbody.innerHTML = Object.entries(stats.persona_matrix).map(([name, p]) => {
          const isCompliant = p.status === 'COMPLIANT';
          const badgeClass = isCompliant 
            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' 
            : 'bg-amber-500/10 text-amber-400 border-amber-500/20';
          const scoreText = p.avg_score ? p.avg_score.toFixed(2) : '--';

          return `
            <tr class="hover:bg-zinc-800/40 transition">
              <td class="py-3 px-4 font-medium text-white flex items-center space-x-2.5">
                <span class="w-2 h-2 rounded-full ${isCompliant ? 'bg-emerald-400' : 'bg-amber-400'}"></span>
                <span>${name}</span>
              </td>
              <td class="py-3 px-4 text-center font-mono">${p.total_jobs}</td>
              <td class="py-3 px-4 text-center font-mono ${p.pass_rate >= 80 ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}">${p.pass_rate}%</td>
              <td class="py-3 px-4 text-center font-mono text-zinc-200">${scoreText}</td>
              <td class="py-3 px-4 text-right font-mono text-purple-300 font-medium">$${(p.total_cost_usd || 0).toFixed(4)}</td>
              <td class="py-3 px-4 text-right font-mono text-zinc-400">${(p.total_tokens || 0).toLocaleString()}</td>
              <td class="py-3 px-4 text-center">
                <span class="px-2.5 py-1 rounded text-[10px] font-semibold border ${badgeClass}">
                  ${isCompliant ? 'Compliant' : 'Review Needed'}
                </span>
              </td>
            </tr>
          `;
        }).join('');
      }

      // 3. Unit Economics & Infrastructure
      const costPerMinEl = document.getElementById('fullFoCostPerMin');
      if (costPerMinEl && stats.unit_economics) {
        costPerMinEl.textContent = `$${stats.unit_economics.cost_per_audio_minute.toFixed(4)} / min`;
      }

      const costPerJobEl = document.getElementById('fullFoCostPerJob');
      if (costPerJobEl && stats.unit_economics) {
        costPerJobEl.textContent = `$${stats.unit_economics.cost_per_job.toFixed(4)} / disclosure`;
      }

      const overheadEl = document.getElementById('fullFoAuditorOverhead');
      if (overheadEl && stats.cost_breakdown) {
        overheadEl.textContent = `${stats.cost_breakdown.judge_cost_percentage}% of total spend`;
      }

      const judgeRatioEl = document.getElementById('fullFoJudgeRatio');
      if (judgeRatioEl && stats.cost_breakdown) {
        judgeRatioEl.textContent = `${stats.cost_breakdown.judge_cost_percentage}% of pipeline spend`;
      }

      const backendRepoEl = document.getElementById('fullFoBackendRepo');
      if (backendRepoEl && stats.gcp_environment) {
        backendRepoEl.textContent = stats.gcp_environment.repository_type === 'FirestoreJobRepository'
          ? 'Firestore Native (tts-jobs)'
          : 'SQLite (Local Test Mode)';
      }

      const bucketNameEl = document.getElementById('fullFoBucketName');
      if (bucketNameEl && stats.gcp_environment) {
        bucketNameEl.textContent = stats.gcp_environment.bucket_name || 'knowledge-to-audio-poc';
      }

      // 4. Flagged Disclosures List
      const flaggedBadge = document.getElementById('fullFoFlaggedBadge');
      if (flaggedBadge) {
        const count = stats.flagged_jobs ? stats.flagged_jobs.length : 0;
        flaggedBadge.textContent = `${count} Flagged`;
        flaggedBadge.className = count === 0
          ? 'text-[10px] px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-medium'
          : 'text-[10px] px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 font-medium';
      }

      const flaggedContainer = document.getElementById('fullFoFlaggedContainer');
      if (flaggedContainer) {
        if (!stats.flagged_jobs || stats.flagged_jobs.length === 0) {
          flaggedContainer.innerHTML = `
            <div class="p-4 bg-emerald-950/20 border border-emerald-500/20 rounded-xl text-center">
              <i data-lucide="check-circle-2" class="w-5 h-5 text-emerald-400 mx-auto mb-1"></i>
              <p class="text-xs text-emerald-300 font-medium">All synthesized audio disclosures meet regulatory quality requirements (&ge; 4.0 / 5.0).</p>
            </div>
          `;
        } else {
          flaggedContainer.innerHTML = stats.flagged_jobs.map(j => `
            <div class="p-3.5 bg-zinc-950/70 border border-amber-800/40 rounded-xl flex items-center justify-between gap-4 hover:border-amber-600/60 transition">
              <div class="space-y-1 min-w-0">
                <div class="flex items-center space-x-2">
                  <span class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-bold font-mono">
                    ${j.overall_score.toFixed(2)} / 5.0
                  </span>
                  <span class="text-xs font-semibold text-white truncate max-w-md lg:max-w-xl">${j.title}</span>
                  <span class="text-[10px] text-zinc-400 font-medium">${j.persona}</span>
                </div>
                <p class="text-[11px] text-zinc-400 line-clamp-1">${j.overall_reasoning}</p>
              </div>
              <button onclick="openJobDetail('${j.job_id}')"
                class="shrink-0 px-3 py-1.5 bg-purple-600/30 hover:bg-purple-600/50 border border-purple-500/40 text-purple-200 text-xs font-semibold rounded-lg transition flex items-center space-x-1.5 shadow-sm">
                <i data-lucide="shield" class="w-3.5 h-3.5 text-purple-300"></i>
                <span>Audit Scorecard</span>
              </button>
            </div>
          `).join('');
        }
      }

      // 5. Radar summary tags
      if (stats.rubric_averages) {
        const entries = Object.values(stats.rubric_averages);
        if (entries.length > 0) {
          const sorted = [...entries].sort((a, b) => (b.avg_score || 0) - (a.avg_score || 0));
          const topDim = sorted[0];
          const lagDim = sorted[sorted.length - 1];
          const topDimEl = document.getElementById('statRadarTopDim');
          const lagDimEl = document.getElementById('statRadarLagDim');
          if (topDimEl && topDim) topDimEl.textContent = `${topDim.label.split('&')[0].trim()} (${topDim.avg_score.toFixed(1)})`;
          if (lagDimEl && lagDim) lagDimEl.textContent = `${lagDim.label.split('&')[0].trim()} (${lagDim.avg_score.toFixed(1)})`;
        }
      }

      lucide.createIcons();
    }

    function renderAuditorCharts(stats) {
      if (typeof Chart === 'undefined') {
        console.warn('Chart.js not yet loaded in DOM');
        return;
      }
      if (!stats) return;

      // 1. Radar Chart: 6 Rubric Dimensions
      const radarCanvas = document.getElementById('chartRubricRadar');
      if (radarCanvas && stats.rubric_averages) {
        if (chartInstances.radar) chartInstances.radar.destroy();

        const labels = [
          'Script Adherence',
          'Naturalness',
          'Pacing & Pauses',
          'Tone Demeanor',
          'Pronunciation',
          'Acoustic Clarity'
        ];
        const keys = [
          'script_adherence_and_accuracy',
          'naturalness_and_inflection',
          'pacing_and_breathing',
          'tone_congruence',
          'pronunciation_and_jargon',
          'acoustic_quality'
        ];
        const scores = keys.map(k => (stats.rubric_averages[k] && stats.rubric_averages[k].avg_score) || 4.0);
        const benchmark = [4.0, 4.0, 4.0, 4.0, 4.0, 4.0];

        chartInstances.radar = new Chart(radarCanvas, {
          type: 'radar',
          data: {
            labels: labels,
            datasets: [
              {
                label: 'Fleet Actual Score',
                data: scores,
                backgroundColor: 'rgba(168, 85, 247, 0.25)',
                borderColor: 'rgb(192, 132, 252)',
                pointBackgroundColor: 'rgb(216, 180, 254)',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: 'rgb(192, 132, 252)',
                borderWidth: 2
              },
              {
                label: 'Regulatory Benchmark (4.0)',
                data: benchmark,
                backgroundColor: 'rgba(16, 185, 129, 0.05)',
                borderColor: 'rgba(52, 211, 153, 0.85)',
                borderDash: [4, 4],
                pointBackgroundColor: 'rgb(52, 211, 153)',
                pointRadius: 2,
                borderWidth: 1.5
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              r: {
                min: 1.0,
                max: 5.0,
                ticks: { stepSize: 1.0, color: '#71717a', backdropColor: 'transparent', font: { family: 'JetBrains Mono', size: 9 } },
                grid: { color: 'rgba(63, 63, 70, 0.4)' },
                angleLines: { color: 'rgba(63, 63, 70, 0.4)' },
                pointLabels: { color: '#d4d4d8', font: { family: 'DM Sans', size: 10, weight: '500' } }
              }
            },
            plugins: {
              legend: {
                position: 'bottom',
                labels: { color: '#a1a1aa', font: { family: 'DM Sans', size: 11 }, boxWidth: 12, padding: 12 }
              }
            }
          }
        });
      }

      // 2. Doughnut Chart: FinOps Spend Allocation
      const costCanvas = document.getElementById('chartFinopsSplit');
      if (costCanvas && stats.cost_breakdown) {
        if (chartInstances.cost) chartInstances.cost.destroy();

        const ttsCost = stats.cost_breakdown.tts_cost_usd || 0;
        const judgeCost = stats.cost_breakdown.judge_cost_usd || 0;

        chartInstances.cost = new Chart(costCanvas, {
          type: 'doughnut',
          data: {
            labels: ['Gemini 3.1 Flash Speech', 'Gemini 3.8 Flash Judge'],
            datasets: [{
              data: [ttsCost, judgeCost],
              backgroundColor: ['rgba(6, 182, 212, 0.85)', 'rgba(168, 85, 247, 0.85)'],
              borderColor: ['#0891b2', '#9333ea'],
              borderWidth: 1.5,
              hoverOffset: 6
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: {
                position: 'bottom',
                labels: { color: '#a1a1aa', font: { family: 'DM Sans', size: 11 }, boxWidth: 12, padding: 12 }
              },
              tooltip: {
                callbacks: {
                  label: function(ctx) {
                    const val = ctx.raw || 0;
                    const total = ttsCost + judgeCost;
                    const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                    return ` ${ctx.label}: $${val.toFixed(4)} (${pct}%)`;
                  }
                }
              }
            },
            cutout: '68%'
          }
        });
      }

      // 3. Bar Chart: Persona Multimodal Quality Benchmarks
      const personaCanvas = document.getElementById('chartPersonaBars');
      if (personaCanvas && stats.persona_matrix) {
        if (chartInstances.persona) chartInstances.persona.destroy();

        const personas = Object.values(stats.persona_matrix);
        const labels = personas.map(p => p.persona);
        const scores = personas.map(p => p.avg_score || 0);
        const backgroundColors = scores.map(s => (s >= 4.0 ? 'rgba(16, 185, 129, 0.75)' : (s > 0 ? 'rgba(245, 158, 11, 0.75)' : 'rgba(113, 113, 122, 0.35)')));
        const borderColors = scores.map(s => (s >= 4.0 ? '#10b981' : (s > 0 ? '#f59e0b' : '#71717a')));

        chartInstances.persona = new Chart(personaCanvas, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [
              {
                label: 'Average Quality Score (1.0 - 5.0)',
                data: scores,
                backgroundColor: backgroundColors,
                borderColor: borderColors,
                borderWidth: 1.5,
                borderRadius: 6
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            scales: {
              x: {
                min: 0,
                max: 5.0,
                ticks: { color: '#71717a', font: { family: 'JetBrains Mono', size: 10 } },
                grid: { color: 'rgba(63, 63, 70, 0.3)' }
              },
              y: {
                ticks: { color: '#e4e4e7', font: { family: 'DM Sans', size: 10, weight: '500' } },
                grid: { display: false }
              }
            },
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  label: function(ctx) {
                    return ` Score: ${ctx.raw > 0 ? ctx.raw.toFixed(2) + ' / 5.0' : 'No disclosures yet'}`;
                  }
                }
              }
            }
          }
        });
      }

      // 4. Bar Chart: Token Utilization by Model (Input vs. Output Tokens)
      const tokenCanvas = document.getElementById('chartTokenStack');
      if (tokenCanvas && (stats.model_matrix || stats.token_breakdown)) {
        if (chartInstances.tokens) chartInstances.tokens.destroy();

        let labels = [];
        let inputData = [];
        let outputData = [];
        let costs = [];

        if (stats.model_matrix) {
          const models = Object.values(stats.model_matrix);
          labels = models.map(m => m.display_name || m.model);
          inputData = models.map(m => m.input_tokens || 0);
          outputData = models.map(m => m.output_tokens || 0);
          costs = models.map(m => m.total_cost_usd || 0);
        } else {
          const tb = stats.token_breakdown || {};
          labels = ['Gemini 3.1 Flash Speech', 'Gemini 3.8 Flash Judge'];
          inputData = [tb.input_text_tokens || 0, tb.judge_input_tokens || 0];
          outputData = [tb.audio_output_tokens || 0, tb.judge_output_tokens || 0];
          costs = [stats.cost_breakdown?.tts_cost_usd || 0, stats.cost_breakdown?.judge_cost_usd || 0];
        }

        chartInstances.tokens = new Chart(tokenCanvas, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [
              {
                label: 'Input Tokens (Prompt)',
                data: inputData,
                backgroundColor: 'rgba(6, 182, 212, 0.8)',
                borderColor: '#06b6d4',
                borderWidth: 1.5,
                borderRadius: 6
              },
              {
                label: 'Output Tokens (Candidate / Audio)',
                data: outputData,
                backgroundColor: 'rgba(168, 85, 247, 0.8)',
                borderColor: '#a855f7',
                borderWidth: 1.5,
                borderRadius: 6
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              y: {
                ticks: {
                  color: '#71717a',
                  font: { family: 'JetBrains Mono', size: 10 },
                  callback: function(v) { return v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v; }
                },
                grid: { color: 'rgba(63, 63, 70, 0.3)' }
              },
              x: {
                ticks: { color: '#e4e4e7', font: { family: 'DM Sans', size: 10, weight: '500' } },
                grid: { display: false }
              }
            },
            plugins: {
              legend: {
                position: 'bottom',
                labels: { color: '#a1a1aa', font: { family: 'DM Sans', size: 10 }, boxWidth: 10, padding: 10 }
              },
              tooltip: {
                callbacks: {
                  label: function(ctx) {
                    return ` ${ctx.dataset.label.split('(')[0].trim()}: ${(ctx.raw || 0).toLocaleString()} tokens`;
                  },
                  afterBody: function(ctxList) {
                    if (ctxList.length > 0 && costs.length > ctxList[0].dataIndex) {
                      const cost = costs[ctxList[0].dataIndex];
                      return ` FinOps Spend: $${cost.toFixed(4)} USD`;
                    }
                    return '';
                  }
                }
              }
            }
          }
        });
      }
    }

    // Escape key closes open modals
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeDetailModal();
        closeNewJobModal();
        closeBulkJobModal();
        closeFinOpsDrawer();
      }
    });

