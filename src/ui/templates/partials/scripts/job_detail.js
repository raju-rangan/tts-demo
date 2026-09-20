    async function openJobDetail(jobId, fallbackJob = null) {
      let job = ALL_JOBS.find(j => j.job_id === jobId) || fallbackJob;
      if (!job) {
        try {
          const resp = await fetch(`/api/jobs/${jobId}`, { headers: getAuthHeaders() });
          if (resp.ok) {
            job = await resp.json();
            const existingIdx = ALL_JOBS.findIndex(j => j.job_id === jobId);
            if (existingIdx !== -1) {
              ALL_JOBS[existingIdx] = job;
            } else {
              ALL_JOBS.unshift(job);
            }
            filterJobs(false);
          }
        } catch (e) {
          console.error("Could not fetch job detail for " + jobId, e);
        }
      }
      if (!job) return;
      CURRENT_JOB = job;

      document.getElementById('detailJobId').textContent = job.job_id;
      document.getElementById('detailTimestamp').textContent = new Date(job.created_at).toUTCString();
      document.getElementById('detailGcsUri').value = job.gcs_uri || 'N/A';
      document.getElementById('detailPrefixKey').textContent = job.audience.includes('External') ? 'external/audio/' : (job.audience.includes('Internal') ? 'internal/audio/' : 'shared/audio/');
      document.getElementById('detailAudioFormat').textContent = job.audio_format || 'MP3 24kHz @ 320kbps';
      document.getElementById('detailSynthesisLatency').textContent = `${(job.synthesis_latency_sec || 0).toFixed(2)}s`;
      const speedVal = (job.speed && !isNaN(job.speed)) ? Number(job.speed).toFixed(2) : '1.00';
      const speedEl = document.getElementById('detailSpeed');
      if (speedEl) speedEl.textContent = `${speedVal}x`;
      const audioEl = document.getElementById('audioElement');
      if (audioEl) {
        audioEl.playbackRate = 1.0;
        if (typeof updatePlaybackRateButtons === 'function') updatePlaybackRateButtons(1.0);
      }
      document.getElementById('detailWordCount').textContent = job.word_count || 0;
      document.getElementById('detailTranscriptText').textContent = job.transcript;

      // Director's Notes / Voice Customization
      const voiceCustCard = document.getElementById('detailVoiceCustomizationCard');
      const voiceCustText = document.getElementById('detailVoiceCustomizationText');
      if (voiceCustCard && voiceCustText) {
        if (job.voice_customization && job.voice_customization.trim()) {
          voiceCustCard.classList.remove('hidden');
          voiceCustText.textContent = `"${job.voice_customization.trim()}"`;
        } else {
          voiceCustCard.classList.add('hidden');
        }
      }

      // Auditor Critique Remediation (for retried/steered jobs)
      const remediationCard = document.getElementById('detailRemediationCard');
      const remediationText = document.getElementById('detailRemediationText');
      const retryCountEl = document.getElementById('detailRetryCount');
      const deltaBadge = document.getElementById('detailScoreDeltaBadge');
      const detailRetryBadge = document.getElementById('detailRetryBadge');

      const retryCount = job.retry_count || 0;
      if (detailRetryBadge) {
        if (retryCount > 0) {
          detailRetryBadge.textContent = `Take ${retryCount + 1}`;
          detailRetryBadge.classList.remove('hidden');
        } else {
          detailRetryBadge.classList.add('hidden');
        }
      }

      if (remediationCard && remediationText) {
        if (job.remediation_prompt && job.remediation_prompt.trim()) {
          remediationCard.classList.remove('hidden');
          remediationText.textContent = job.remediation_prompt.trim();
          if (retryCountEl) retryCountEl.textContent = retryCount + 1;
          if (deltaBadge) {
            if (job.previous_attempt_score && job.overall_score) {
              const diff = job.overall_score - job.previous_attempt_score;
              const sign = diff >= 0 ? '+' : '';
              deltaBadge.textContent = `Take ${retryCount}: ${job.previous_attempt_score.toFixed(1)} ➔ Take ${retryCount + 1}: ${job.overall_score.toFixed(1)} (${sign}${diff.toFixed(1)})`;
              deltaBadge.classList.remove('hidden');
            } else {
              deltaBadge.classList.add('hidden');
            }
          }
        } else {
          remediationCard.classList.add('hidden');
        }
      }

      // Source Web URL (for bulk processed jobs)
      const sourceCard = document.getElementById('detailSourceUrlCard');
      const sourceInput = document.getElementById('detailSourceUrlInput');
      const sourceLink = document.getElementById('detailSourceUrlLink');
      const sourceDomain = document.getElementById('detailSourceUrlDomain');
      if (sourceCard && sourceInput) {
        if (job.source_url) {
          sourceCard.classList.remove('hidden');
          sourceInput.value = job.source_url;
          sourceLink.href = job.source_url;
          try {
            sourceDomain.textContent = new URL(job.source_url).hostname;
          } catch(e) {
            sourceDomain.textContent = 'Visit Source';
          }
        } else {
          sourceCard.classList.add('hidden');
        }
      }

      const statusBadge = document.getElementById('detailStatusBadge');
      const errBanner = document.getElementById('jobErrorBanner');
      const runningBanner = document.getElementById('jobRunningBanner');
      const audioCard = document.getElementById('audioPlayerCard');
      const scorecardCard = document.getElementById('scorecardCard');
      const reasoningContainer = document.getElementById('overallReasoningContainer');
      const retryBtn = document.getElementById('modalRetryBtn');
      const deleteBtn = document.getElementById('modalDeleteBtn');

      if (CURRENT_PERSONA === 'auditor') {
        if (retryBtn) retryBtn.classList.add('hidden');
        if (deleteBtn) deleteBtn.classList.add('hidden');
      } else {
        if (deleteBtn) deleteBtn.classList.remove('hidden');
        if (retryBtn) {
          retryBtn.classList.remove('hidden');
          if (job.status === 'RUNNING') {
            retryBtn.disabled = true;
            retryBtn.classList.add('opacity-50', 'cursor-not-allowed');
            retryBtn.title = 'Synthesis is currently running in background';
          } else {
            retryBtn.disabled = false;
            retryBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            retryBtn.title = 'Retry Voice Synthesis';
          }
        }
      }

      if (job.status === 'RUNNING') {
        statusBadge.textContent = 'RUNNING';
        statusBadge.className = 'px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse';
        runningBanner.classList.remove('hidden');
        errBanner.classList.add('hidden');
        audioCard.classList.add('hidden');
        scorecardCard.classList.add('hidden');
        reasoningContainer.classList.add('hidden');

        // Update Live Progress Screen
        const currentStage = (job.progress_stage || 'SYNTHESIZING').toUpperCase();
        document.getElementById('runningStagePill').textContent = currentStage;
        document.getElementById('runningMessageText').textContent = job.progress_message || 'Executing speech generation pipeline...';

        // Multi-Turn Progress Indicator
        const turnsContainer = document.getElementById('runningTurnsContainer');
        const turnsPills = document.getElementById('runningTurnsPills');
        const turnCounter = document.getElementById('runningTurnCounter');
        if (job.total_turns && job.total_turns > 1) {
          turnsContainer.classList.remove('hidden');
          const curTurn = job.current_turn || 1;
          turnCounter.textContent = `Turn ${curTurn} of ${job.total_turns}`;
          let pillsHtml = '';
          for (let t = 1; t <= job.total_turns; t++) {
            if (t < curTurn) {
              pillsHtml += `<span class="px-2 py-0.5 bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 rounded text-[10px] font-mono flex items-center space-x-1"><i data-lucide="check" class="w-3 h-3"></i><span>Turn ${t} Done</span></span>`;
            } else if (t === curTurn && (currentStage === 'SYNTHESIZING' || currentStage === 'CHUNKING')) {
              pillsHtml += `<span class="px-2 py-0.5 bg-amber-500/20 text-amber-300 border border-amber-500/40 rounded text-[10px] font-mono flex items-center space-x-1 animate-pulse"><i data-lucide="loader-2" class="w-3 h-3 animate-spin"></i><span>Turn ${t} Synthesizing</span></span>`;
            } else if (t === curTurn && currentStage !== 'SYNTHESIZING' && currentStage !== 'CHUNKING') {
              pillsHtml += `<span class="px-2 py-0.5 bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 rounded text-[10px] font-mono flex items-center space-x-1"><i data-lucide="check" class="w-3 h-3"></i><span>Turn ${t} Synthesized</span></span>`;
            } else {
              pillsHtml += `<span class="px-2 py-0.5 bg-zinc-800/60 text-zinc-500 border border-zinc-700/40 rounded text-[10px] font-mono">Turn ${t}</span>`;
            }
          }
          turnsPills.innerHTML = pillsHtml;
        } else {
          turnsContainer.classList.add('hidden');
        }

        // 5-Stage Stepper Update
        const stages = ['CHUNKING', 'SYNTHESIZING', 'STITCHING', 'UPLOADING', 'EVALUATING'];
        const stageIdx = stages.indexOf(currentStage) !== -1 ? stages.indexOf(currentStage) : 1;
        const stepConfigs = [
          { id: 'stepChunking', iconId: 'stepChunkingIcon', statusId: 'stepChunkingStatus', num: 1 },
          { id: 'stepSynthesizing', iconId: 'stepSynthesizingIcon', statusId: 'stepSynthesizingStatus', num: 2 },
          { id: 'stepStitching', iconId: 'stepStitchingIcon', statusId: 'stepStitchingStatus', num: 3 },
          { id: 'stepUploading', iconId: 'stepUploadingIcon', statusId: 'stepUploadingStatus', num: 4 },
          { id: 'stepEvaluating', iconId: 'stepEvaluatingIcon', statusId: 'stepEvaluatingStatus', num: 5 }
        ];

        stepConfigs.forEach((sc, idx) => {
          const el = document.getElementById(sc.id);
          const iconEl = document.getElementById(sc.iconId);
          const statEl = document.getElementById(sc.statusId);
          if (!el || !iconEl || !statEl) return;

          if (idx < stageIdx) {
            el.className = 'flex items-center space-x-3 p-2 rounded-xl border border-emerald-800/50 bg-emerald-950/20 transition';
            iconEl.className = 'w-5 h-5 rounded-full flex items-center justify-center shrink-0 text-[10px] font-bold bg-emerald-500 text-zinc-950 font-mono';
            iconEl.innerHTML = '<i data-lucide="check" class="w-3 h-3"></i>';
            statEl.className = 'text-[11px] font-mono text-emerald-400 font-semibold shrink-0';
            statEl.textContent = 'Completed';
          } else if (idx === stageIdx) {
            el.className = 'flex items-center space-x-3 p-2 rounded-xl border border-amber-500/50 bg-amber-950/30 transition animate-pulse';
            iconEl.className = 'w-5 h-5 rounded-full flex items-center justify-center shrink-0 text-[10px] font-bold bg-amber-500 text-zinc-950 font-mono';
            iconEl.innerHTML = '<i data-lucide="loader-2" class="w-3 h-3 animate-spin"></i>';
            statEl.className = 'text-[11px] font-mono text-amber-400 font-bold shrink-0';
            statEl.textContent = 'Active';
          } else {
            el.className = 'flex items-center space-x-3 p-2 rounded-xl border border-zinc-800/60 bg-zinc-900/40 transition';
            iconEl.className = 'w-5 h-5 rounded-full flex items-center justify-center shrink-0 text-[10px] font-bold bg-zinc-800 text-zinc-500 font-mono';
            iconEl.textContent = sc.num;
            statEl.className = 'text-[11px] font-mono text-zinc-500 shrink-0';
            statEl.textContent = 'Pending';
          }
        });
      } else if (job.status === 'FAILED') {
        statusBadge.textContent = 'FAILED';
        statusBadge.className = 'px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20';
        runningBanner.classList.add('hidden');
        errBanner.classList.remove('hidden');
        document.getElementById('jobErrorTitle').textContent = 'Speech Generation Failed';
        document.getElementById('jobErrorMessage').textContent = job.error_message || 'The Gemini TTS engine encountered an error during audio generation. Verify model quota and article length.';
        audioCard.classList.add('hidden');
        scorecardCard.classList.add('hidden');
        reasoningContainer.classList.add('hidden');
      } else {
        statusBadge.textContent = 'COMPLETED';
        statusBadge.className = 'px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
        runningBanner.classList.add('hidden');
        audioCard.classList.remove('hidden');

        // Audio Source
        const audioEl = document.getElementById('audioElement');
        audioEl.src = `/api/audio/${job.job_id}`;
        document.getElementById('downloadAudioLink').href = `/api/audio/${job.job_id}`;

        // Evaluation Warning
        if (job.error_message) {
          errBanner.classList.remove('hidden');
          document.getElementById('jobErrorTitle').textContent = 'Quality Audit Notice';
          document.getElementById('jobErrorMessage').textContent = job.error_message;
        } else {
          errBanner.classList.add('hidden');
        }

        // Overall Reasoning
        if (job.overall_reasoning) {
          reasoningContainer.classList.remove('hidden');
          document.getElementById('detailOverallReasoning').textContent = job.overall_reasoning;
        } else {
          reasoningContainer.classList.add('hidden');
        }
      }

      // Token & Cost Breakdown
      if (job.token_usage) {
        document.getElementById('tokenTextInput').textContent = (job.token_usage.input_text_tokens || 0).toLocaleString();
        document.getElementById('tokenAudioOutput').textContent = (job.token_usage.audio_output_tokens || 0).toLocaleString();
        document.getElementById('tokenJudge').textContent = ((job.token_usage.judge_input_tokens || 0) + (job.token_usage.judge_output_tokens || 0)).toLocaleString();
      }
      if (job.cost) {
        document.getElementById('costTotalUsd').textContent = `$${job.cost.total_cost_usd.toFixed(6)}`;
        document.getElementById('costTtsUsd').textContent = `$${job.cost.tts_cost_usd.toFixed(6)}`;
        document.getElementById('costJudgeUsd').textContent = `$${job.cost.judge_cost_usd.toFixed(6)}`;
      }

      // Quality Scorecard
      if (job.overall_score !== null && job.overall_score !== undefined) {
        scorecardCard.classList.remove('hidden');
        document.getElementById('detailOverallScore').textContent = job.overall_score.toFixed(2);
        document.getElementById('detailJudgeModel').textContent = job.judge_model || 'gemini-3.8-flash';
        
        const verdictEl = document.getElementById('detailVerdictBadge');
        if (job.passed_rubric) {
          verdictEl.textContent = 'PASSED QUALITY GATE';
          verdictEl.className = 'px-2 py-0.5 rounded text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
        } else {
          verdictEl.textContent = 'NEEDS REVISION';
          verdictEl.className = 'px-2 py-0.5 rounded text-xs font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20';
        }

        // Render rubric dimensions
        const listEl = document.getElementById('rubricDimensionsList');
        if (job.rubric_metrics) {
          listEl.innerHTML = Object.entries(job.rubric_metrics).map(([key, metric]) => {
            const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            const percent = (metric.score / 5.0) * 100;
            const barColor = metric.score >= 4.0 ? 'bg-emerald-500' : (metric.score >= 3.0 ? 'bg-amber-500' : 'bg-rose-500');

            return `
              <div class="p-3 bg-zinc-900 border border-zinc-800/80 rounded-xl space-y-1.5">
                <div class="flex items-center justify-between text-xs">
                  <span class="font-semibold text-zinc-200">${label} <span class="text-[10px] text-zinc-500">(${parseInt(metric.weight * 100)}%)</span></span>
                  <span class="font-mono font-bold text-zinc-100">${metric.score.toFixed(1)} / 5.0</span>
                </div>
                <div class="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                  <div class="${barColor} h-full rounded-full transition-all" style="width: ${percent}%"></div>
                </div>
                <p class="text-[11px] text-zinc-400 italic mt-1">${metric.rationale}</p>
              </div>
            `;
          }).join('');
        }

        // Actionable feedback
        const feedbackContainer = document.getElementById('actionableFeedbackContainer');
        const feedbackList = document.getElementById('actionableFeedbackList');
        if (job.actionable_feedback && job.actionable_feedback.length > 0) {
          feedbackContainer.classList.remove('hidden');
          feedbackList.innerHTML = job.actionable_feedback.map(f => `<li>${f}</li>`).join('');
        } else {
          feedbackContainer.classList.add('hidden');
        }
      } else {
        scorecardCard.classList.add('hidden');
      }

      document.getElementById('jobDetailModal').classList.remove('hidden');
      lucide.createIcons();

      if (CURRENT_PERSONA === 'auditor' && job.overall_score !== null && job.overall_score !== undefined) {
        setTimeout(() => {
          const scrollable = document.querySelector('#jobDetailModal .overflow-y-auto');
          const scorecardEl = document.getElementById('scorecardCard');
          if (scrollable && scorecardEl) {
            scorecardEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }
        }, 120);
      }
    }

    function closeDetailModal() {
      const audioEl = document.getElementById('audioElement');
      if (audioEl) audioEl.pause();
      document.getElementById('jobDetailModal').classList.add('hidden');
      CURRENT_JOB = null;
    }

    async function deleteJob(jobId, event) {
      if (event) event.stopPropagation();
      if (!confirm(`Are you sure you want to permanently delete job ${jobId}? This will remove the database record and audio artifacts.`)) {
        return;
      }
      try {
        const resp = await fetch(`/api/jobs/${jobId}`, {
          method: 'DELETE',
          headers: getAuthHeaders()
        });
        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          alert(`Failed to delete job: ${errData.detail || resp.statusText}`);
          return;
        }
        // Remove from local array
        ALL_JOBS = ALL_JOBS.filter(j => j.job_id !== jobId);
        filterJobs(false);
        await loadStats();
        if (CURRENT_JOB && CURRENT_JOB.job_id === jobId) {
          closeDetailModal();
        }
      } catch (err) {
        alert(`Error deleting job: ${err.message}`);
      }
    }

    async function deleteCurrentJob() {
      if (!CURRENT_JOB) return;
      await deleteJob(CURRENT_JOB.job_id);
    }

    let ACTIVE_RETRY_JOB_ID = null;
    let DEFAULT_RETRY_CRITIQUE = '';

