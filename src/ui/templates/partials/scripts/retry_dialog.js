    function toggleRetryCritiqueInput(enabled) {
      const box = document.getElementById('retryCritiqueBox');
      if (box) {
        if (enabled) {
          box.classList.remove('opacity-40', 'pointer-events-none');
        } else {
          box.classList.add('opacity-40', 'pointer-events-none');
        }
      }
    }

    function resetRetryCritiqueToDefault() {
      const txt = document.getElementById('retryCritiqueText');
      if (txt) txt.value = DEFAULT_RETRY_CRITIQUE;
    }

    function updateRetrySpeedDisplay(val) {
      const num = parseFloat(val);
      const disp = document.getElementById('retrySpeedDisplay');
      if (disp) disp.textContent = `${num.toFixed(2)}x`;
    }

    function setRetrySpeedPreset(val) {
      const slider = document.getElementById('retrySpeed');
      if (slider) {
        slider.value = val;
        updateRetrySpeedDisplay(val);
      }
    }

    function closeRetryModal() {
      const modal = document.getElementById('modalRetryDialog');
      if (modal) modal.classList.add('hidden');
      ACTIVE_RETRY_JOB_ID = null;
    }

    async function openRetryModal(jobId, event) {
      if (event) event.stopPropagation();
      if (!jobId) {
        if (CURRENT_JOB) jobId = CURRENT_JOB.job_id;
        else return;
      }
      ACTIVE_RETRY_JOB_ID = jobId;

      const modal = document.getElementById('modalRetryDialog');
      if (modal) modal.classList.remove('hidden');

      const takeBadge = document.getElementById('retryTakeBadge');
      const prevScoreBadge = document.getElementById('retryPrevScoreBadge');
      const prevGateBadge = document.getElementById('retryPrevGateBadge');
      const prevReasoning = document.getElementById('retryPrevReasoning');
      const flaggedContainer = document.getElementById('retryFlaggedContainer');
      const flaggedList = document.getElementById('retryFlaggedList');
      const critiqueText = document.getElementById('retryCritiqueText');
      const voiceCustInput = document.getElementById('retryVoiceCustomization');
      const speedSlider = document.getElementById('retrySpeed');
      const includeCritiqueCb = document.getElementById('retryIncludeCritique');

      if (includeCritiqueCb) includeCritiqueCb.checked = true;
      toggleRetryCritiqueInput(true);

      try {
        const resp = await fetch(`/api/jobs/${jobId}/retry-preview`, {
          headers: getAuthHeaders()
        });
        if (!resp.ok) {
          throw new Error(`Preview failed: ${resp.statusText}`);
        }
        const data = await resp.json();

        const currentTake = (data.retry_count || 0) + 1;
        const nextTake = currentTake + 1;
        if (takeBadge) takeBadge.textContent = `Take ${nextTake}`;

        if (prevScoreBadge) {
          if (data.overall_score !== null && data.overall_score !== undefined) {
            prevScoreBadge.textContent = `${Number(data.overall_score).toFixed(1)} / 5.0`;
            if (data.overall_score >= 4.0) {
              prevScoreBadge.className = 'text-xs font-bold px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
            } else {
              prevScoreBadge.className = 'text-xs font-bold px-2.5 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30';
            }
          } else {
            prevScoreBadge.textContent = 'Unscored';
            prevScoreBadge.className = 'text-xs font-bold px-2.5 py-0.5 rounded-full bg-zinc-800 text-zinc-300';
          }
        }

        if (prevGateBadge) {
          if (data.passed_rubric !== null && data.passed_rubric !== undefined) {
            prevGateBadge.textContent = data.passed_rubric ? 'Passed Compliance Gate' : 'Failed Compliance Gate';
            prevGateBadge.className = data.passed_rubric
              ? 'text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : 'text-[11px] font-medium px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20';
          } else {
            prevGateBadge.textContent = 'Pending Audit';
            prevGateBadge.className = 'text-[11px] font-medium px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400';
          }
        }

        if (prevReasoning) {
          prevReasoning.textContent = data.overall_reasoning || 'No auditor evaluation findings recorded for previous take.';
        }

        // Flagged deductions
        if (flaggedContainer && flaggedList) {
          if (data.flagged_metrics && data.flagged_metrics.length > 0) {
            flaggedList.innerHTML = data.flagged_metrics.map(m => `
              <div class="flex items-start space-x-2">
                <span class="text-rose-400 font-bold shrink-0">•</span>
                <div>
                  <span class="font-semibold text-rose-200">${m.label} (${Number(m.score).toFixed(1)}/5.0):</span>
                  <span class="text-zinc-300 ml-1">${m.rationale}</span>
                </div>
              </div>
            `).join('');
            flaggedContainer.classList.remove('hidden');
          } else {
            flaggedList.innerHTML = '';
            flaggedContainer.classList.add('hidden');
          }
        }

        DEFAULT_RETRY_CRITIQUE = data.suggested_directive || '';
        if (critiqueText) critiqueText.value = DEFAULT_RETRY_CRITIQUE;

        if (voiceCustInput) voiceCustInput.value = data.voice_customization || '';
        if (speedSlider) {
          const spd = data.speed || 1.0;
          speedSlider.value = spd;
          updateRetrySpeedDisplay(spd);
        }
      } catch (err) {
        console.warn('Could not load retry preview, using defaults:', err);
        DEFAULT_RETRY_CRITIQUE = '';
        if (critiqueText) critiqueText.value = '';
        if (prevReasoning) prevReasoning.textContent = 'Unable to fetch prior evaluation preview.';
      }

      lucide.createIcons();
    }

    async function confirmAndExecuteRetry() {
      if (!ACTIVE_RETRY_JOB_ID) return;
      const jobId = ACTIVE_RETRY_JOB_ID;
      const btn = document.getElementById('confirmRetrySubmitBtn');
      const icon = document.getElementById('retrySubmitIcon');
      const text = document.getElementById('retrySubmitText');

      if (btn) btn.disabled = true;
      if (icon) icon.classList.add('animate-spin');
      if (text) text.textContent = 'Launching Re-Synthesis...';

      const includeCritique = document.getElementById('retryIncludeCritique')?.checked ?? true;
      const customCritique = document.getElementById('retryCritiqueText')?.value || '';
      const speed = parseFloat(document.getElementById('retrySpeed')?.value || '1.0');
      const voiceCustomization = document.getElementById('retryVoiceCustomization')?.value || null;

      try {
        const resp = await fetch(`/api/jobs/${jobId}/retry`, {
          method: 'POST',
          headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({
            include_critique: includeCritique,
            custom_critique: customCritique,
            speed: speed,
            voice_customization: voiceCustomization
          })
        });

        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          alert(`Failed to retry job: ${errData.detail || resp.statusText}`);
          return;
        }

        const data = await resp.json();
        // Update job in local ALL_JOBS array
        const idx = ALL_JOBS.findIndex(j => j.job_id === jobId);
        if (idx !== -1) {
          ALL_JOBS[idx] = data.job;
        } else {
          ALL_JOBS.unshift(data.job);
        }
        filterJobs(false);
        await loadStats();

        // Refresh detail modal if open
        const modalEl = document.getElementById('jobDetailModal');
        const isModalOpen = modalEl && !modalEl.classList.contains('hidden');
        if (isModalOpen && CURRENT_JOB && CURRENT_JOB.job_id === jobId) {
          CURRENT_JOB = data.job;
          openJobDetail(jobId);
        }

        closeRetryModal();
        checkAndStartPolling();
      } catch (err) {
        alert(`Error retrying job: ${err.message}`);
      } finally {
        if (btn) btn.disabled = false;
        if (icon) icon.classList.remove('animate-spin');
        if (text) text.textContent = 'Confirm & Launch Re-Synthesis';
      }
    }

    async function retryCurrentJob() {
      if (!CURRENT_JOB) return;
      await openRetryModal(CURRENT_JOB.job_id);
    }

    // Copy to Clipboard Utility
    function copyToClipboard(elementId) {
      const el = document.getElementById(elementId);
      const text = el.value !== undefined ? el.value : el.innerText;
      navigator.clipboard.writeText(text).then(() => {
        alert('Copied to clipboard!');
      });
    }

    // New Job Modal
