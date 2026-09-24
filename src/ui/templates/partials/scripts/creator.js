    function openNewJobModal() {
      const statusBox = document.getElementById('newJobStatus');
      if (statusBox) {
        statusBox.className = 'hidden p-3 rounded-xl bg-zinc-950 border border-zinc-800 text-xs flex items-center space-x-2';
        statusBox.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin text-emerald-400"></i><span id="newJobStatusText" class="text-zinc-300">Enqueuing speech generation in background...</span>';
      }
      document.getElementById('newJobModal').classList.remove('hidden');
      updateInputStats();
      lucide.createIcons();
    }

    // Speech Speed & Playback Rate Control Helpers (Gemini TTS)
    function updateSpeedDisplay(val) {
      const num = parseFloat(val);
      const badge = document.getElementById('speedValueBadge');
      if (!badge) return;
      let label = 'Normal';
      if (num < 0.95) label = 'Measured';
      else if (num > 1.05 && num <= 1.30) label = 'Brisk';
      else if (num > 1.30) label = 'Disclaimer';
      badge.textContent = `${num.toFixed(2)}x ${label}`;
      
      document.querySelectorAll('.speed-preset-btn').forEach(btn => {
        const btnVal = parseFloat(btn.textContent);
        if (Math.abs(btnVal - num) < 0.04) {
          btn.className = 'speed-preset-btn px-2 py-0.5 rounded text-[11px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 transition font-semibold';
        } else {
          btn.className = 'speed-preset-btn px-2 py-0.5 rounded text-[11px] font-mono bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 transition';
        }
      });
    }

    function setSpeedPreset(val) {
      const slider = document.getElementById('inputSpeed');
      if (slider) {
        slider.value = val;
        updateSpeedDisplay(val);
      }
    }

    function updateBulkSpeedDisplay(val) {
      const num = parseFloat(val);
      const badge = document.getElementById('bulkSpeedValueBadge');
      if (!badge) return;
      let label = 'Normal';
      if (num < 0.95) label = 'Measured';
      else if (num > 1.05 && num <= 1.30) label = 'Brisk';
      else if (num > 1.30) label = 'Disclaimer';
      badge.textContent = `${num.toFixed(2)}x ${label}`;

      document.querySelectorAll('.bulk-speed-preset-btn').forEach(btn => {
        const btnVal = parseFloat(btn.textContent);
        if (Math.abs(btnVal - num) < 0.04) {
          btn.className = 'bulk-speed-preset-btn px-2 py-0.5 rounded text-[11px] font-mono bg-teal-500/10 text-teal-400 border border-teal-500/30 transition font-semibold';
        } else {
          btn.className = 'bulk-speed-preset-btn px-2 py-0.5 rounded text-[11px] font-mono bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 transition';
        }
      });
    }

    function setBulkSpeedPreset(val) {
      const slider = document.getElementById('inputBulkSpeed');
      if (slider) {
        slider.value = val;
        updateBulkSpeedDisplay(val);
      }
    }

    function setPlaybackRate(rate) {
      const audioEl = document.getElementById('audioElement');
      if (audioEl) {
        audioEl.playbackRate = rate;
      }
      updatePlaybackRateButtons(rate);
    }

    function updatePlaybackRateButtons(rate) {
      document.querySelectorAll('.playback-rate-btn').forEach(btn => {
        const btnRate = parseFloat(btn.textContent);
        if (Math.abs(btnRate - rate) < 0.05) {
          btn.className = 'playback-rate-btn px-1.5 py-0.5 rounded text-[10px] font-mono bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 transition';
        } else {
          btn.className = 'playback-rate-btn px-1.5 py-0.5 rounded text-[10px] font-mono bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition';
        }
      });
    }

    function closeNewJobModal() {
      document.getElementById('newJobModal').classList.add('hidden');
      const statusBox = document.getElementById('newJobStatus');
      if (statusBox) {
        statusBox.className = 'hidden p-3 rounded-xl bg-zinc-950 border border-zinc-800 text-xs flex items-center space-x-2';
        statusBox.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin text-emerald-400"></i><span id="newJobStatusText" class="text-zinc-300">Enqueuing speech generation in background...</span>';
      }
      const voiceInput = document.getElementById('inputVoiceCustomization');
      if (voiceInput) voiceInput.value = '';
      const scriptInput = document.getElementById('inputPodcastScript');
      if (scriptInput) scriptInput.value = '';
      const draftStatus = document.getElementById('podcastDraftStatus');
      if (draftStatus) draftStatus.classList.add('hidden');
      updatePodcastScriptStats();
      const speedSlider = document.getElementById('inputSpeed');
      if (speedSlider) {
        speedSlider.value = '1.0';
        updateSpeedDisplay('1.0');
      }
    }

    function updateInputStats() {
      const text = document.getElementById('inputText').value.trim();
      const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
      const chars = text.length;
      document.getElementById('inputWordCount').textContent = `${words.toLocaleString()} words • ${chars.toLocaleString()} characters`;
      
      const warningEl = document.getElementById('inputWordWarning');
      const warningText = document.getElementById('inputWordWarningText');
      if (words > 400) {
        const turns = Math.ceil(words / 400);
        warningText.textContent = `Long article (${words.toLocaleString()} words): Auto-split into ${turns} complete-sentence turns (~400 words/turn) & stitched losslessly.`;
        warningEl.classList.remove('hidden');
      } else {
        warningEl.classList.add('hidden');
      }
    }

    function updatePodcastScriptStats() {
      const scriptText = document.getElementById('inputPodcastScript')?.value?.trim() || '';
      const statsEl = document.getElementById('podcastScriptStats');
      if (!statsEl) return;
      if (!scriptText) {
        statsEl.textContent = '0 words • ~0.0 mins';
        return;
      }
      const words = scriptText.split(/\s+/).filter(Boolean).length;
      const mins = (words / 150.0).toFixed(1);
      const turns = (scriptText.match(/^\s*\*\*[^*]+\*\*/gm) || []).length;
      const turnLabel = turns > 0 ? ` • ${turns} turns` : '';
      statsEl.textContent = `${words.toLocaleString()} words${turnLabel} • ~${mins} mins`;
    }

    function handlePersonaChange(personaName) {
      const isPodcast = personaName && personaName.startsWith('Podcast:');
      const labelText = document.getElementById('textVoiceCustomizationLabel');
      const badgeTag = document.getElementById('badgeVoiceCustomizationTag');
      const sampleBtn = document.getElementById('btnSampleDirectives');
      const inputCustom = document.getElementById('inputVoiceCustomization');
      const helpText = document.getElementById('helpVoiceCustomization');
      const studioCard = document.getElementById('podcastScriptStudioCard');

      if (isPodcast) {
        if (labelText) labelText.textContent = "Podcast Content Directives & Host Dynamics";
        if (badgeTag) badgeTag.textContent = "Director's Notes (Podcast Required/Recommended)";
        if (sampleBtn) sampleBtn.classList.remove('hidden');
        if (inputCustom) inputCustom.placeholder = "e.g. Unpack interest rate risks, have Host 1 play the skeptical saver, and debate liquidity vs. yield...";
        if (helpText) helpText.textContent = "Guides Gemini 3.8 Flash to write a 2-person podcast dialogue focused on these directions before multi-speaker synthesis.";
        if (studioCard) studioCard.classList.remove('hidden');
      } else {
        if (labelText) labelText.textContent = "Voice Customization & Delivery Directives";
        if (badgeTag) badgeTag.textContent = "Director's Notes (Optional)";
        if (sampleBtn) sampleBtn.classList.add('hidden');
        if (inputCustom) inputCustom.placeholder = "e.g. Speak with an empathetic, reassuring tone and slightly slower cadence on regulatory disclosures...";
        if (helpText) helpText.textContent = "Directly guides pacing, vocal warmth, emphasis, or emotional nuance in Gemini TTS generation.";
        if (studioCard) studioCard.classList.add('hidden');
      }
    }

    async function draftPodcastScript() {
      const text = document.getElementById('inputText')?.value?.trim() || '';
      if (!text || text.length < 10) {
        alert('Please enter or load article text in the "Article / Knowledge Transcript" field first.');
        document.getElementById('inputText')?.focus();
        return;
      }

      const persona = document.getElementById('inputPersona')?.value || 'Podcast: Co-Hosts (Man & Woman)';
      const voice_customization = document.getElementById('inputVoiceCustomization')?.value?.trim() || null;
      const enable_web_search = document.getElementById('inputEnableWebSearch')?.checked ?? true;

      const btn = document.getElementById('btnDraftPodcastScript');
      const btnText = document.getElementById('btnDraftPodcastScriptText');
      const statusBox = document.getElementById('podcastDraftStatus');
      const statusText = document.getElementById('podcastDraftStatusText');
      const scriptArea = document.getElementById('inputPodcastScript');

      if (btn) btn.disabled = true;
      if (btnText) btnText.textContent = 'Drafting Script...';
      if (statusBox) {
        statusBox.className = 'p-3 rounded-xl bg-purple-950/40 border border-purple-800/50 text-xs flex items-center space-x-2 text-purple-200';
        if (statusText) {
          statusText.textContent = enable_web_search
            ? 'Grounding with Google Search & crafting ~10-minute lively dialogue (Gemini 3.8 Flash)...'
            : 'Drafting ~10-minute lively dialogue with vocal cues (Gemini 3.8 Flash)...';
        }
        statusBox.classList.remove('hidden');
      }
      lucide.createIcons();

      try {
        const resp = await fetch('/api/podcast/draft-script', {
          method: 'POST',
          headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({
            text: text,
            persona: persona,
            voice_customization: voice_customization,
            target_duration_mins: 10,
            enable_web_search: enable_web_search
          })
        });

        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.detail || data.message || 'Failed to draft podcast script');
        }

        if (scriptArea && data.markdown_script) {
          scriptArea.value = data.markdown_script;
          updatePodcastScriptStats();
        }

        if (statusBox) {
          statusBox.className = 'p-3 rounded-xl bg-emerald-950/40 border border-emerald-800/60 text-xs flex items-center space-x-2 text-emerald-300';
          statusBox.innerHTML = `<i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-400 shrink-0"></i><span>Generated ${data.word_count.toLocaleString()} words (${data.turn_count} turns, ~${data.estimated_duration_mins} mins) with natural expressions! Review and edit anytime below.</span>`;
          lucide.createIcons();
        }
      } catch (err) {
        if (statusBox) {
          statusBox.className = 'p-3 rounded-xl bg-rose-950/40 border border-rose-800/60 text-xs flex items-center space-x-2 text-rose-300';
          statusBox.innerHTML = `<i data-lucide="alert-circle" class="w-4 h-4 text-rose-400 shrink-0"></i><span>Error: ${err.message}</span>`;
          lucide.createIcons();
        }
      } finally {
        if (btn) btn.disabled = false;
        if (btnText) btnText.textContent = 'Re-Draft 10-Min Script';
      }
    }

    function loadSamplePodcastDirectives() {
      const voiceCust = document.getElementById('inputVoiceCustomization');
      if (voiceCust) {
        voiceCust.value = "Follow the NotebookLM style: open with an evocative thought-experiment ('Imagine logging into your banking dashboard on a random Tuesday...'), have Host 2 push back with healthy skepticism, use vivid real-world analogies (nightclub bouncer, dumb vault), and end with a provocative cliffhanger question for the executive listener.";
      }
    }

    function loadSampleDirectives() {
      const persona = document.getElementById('inputPersona')?.value || '';
      if (persona.startsWith('Podcast:')) {
        loadSamplePodcastDirectives();
      } else {
        const voiceCust = document.getElementById('inputVoiceCustomization');
        if (voiceCust) {
          voiceCust.value = "Speak with an articulate, reassuring retail banking demeanor. Enunciate 'High-Yield' and acronyms FDIC, APY, CD with precision.";
        }
      }
    }

    function loadSampleText() {
      document.getElementById('inputText').value = `High-Yield Savings Accounts vs. Certificates of Deposit (CDs): A Financial Guide for Retail Banking Customers.\n\nWhen planning your short-to-medium-term savings strategy, two of the most secure instruments available are High-Yield Savings Accounts (HYSA) and Certificates of Deposit (CDs). Both products are FDIC-insured up to $250,000 per depositor, per institution, offering principal protection alongside competitive yields.\n\n1. High-Yield Savings Accounts: Flexibility & Liquidity. A high-yield savings account is an interest-bearing deposit account that typically offers an Annual Percentage Yield (APY) significantly higher than traditional brick-and-mortar savings accounts. The defining advantage is liquidity: funds can be deposited or withdrawn at any time via electronic funds transfers (EFT) or Automated Clearing House (ACH) withdrawals, subject to standard federal and bank transaction limits. These accounts are ideal for emergency funds or near-term expenses.\n\n2. Certificates of Deposit: Guaranteed Rate Certainty. A CD is a time-deposit account where you commit a lump sum for a fixed term—ranging from 3 months to 5 years—in exchange for a guaranteed APY that remains locked regardless of Federal Reserve interest rate fluctuations. However, withdrawing funds prior to the maturity date triggers an early withdrawal penalty, typically calculated as several months of interest.\n\n3. Regulatory & Compliance Safeguards. Both HYSAs and CDs require standard Customer Identification Programs (CIP) and Know Your Customer (KYC) verification in accordance with the Bank Secrecy Act (BSA) and anti-money laundering (AML) regulations.`;
      const persona = document.getElementById('inputPersona')?.value || '';
      if (persona.startsWith('Podcast:')) {
        loadSamplePodcastDirectives();
      } else {
        const voiceCust = document.getElementById('inputVoiceCustomization');
        if (voiceCust) {
          voiceCust.value = "Speak with an articulate, reassuring retail banking demeanor. Enunciate 'High-Yield' and acronyms FDIC, APY, CD with precision.";
        }
      }
      updateInputStats();
    }

    async function submitNewJob(e) {
      e.preventDefault();
      const text = document.getElementById('inputText').value.trim();
      const persona = document.getElementById('inputPersona').value;
      const voice_customization = document.getElementById('inputVoiceCustomization')?.value?.trim() || null;
      const speed = parseFloat(document.getElementById('inputSpeed')?.value || '1.0');
      const run_judge = document.getElementById('inputRunJudge').checked;
      const podcast_script = persona.startsWith('Podcast:')
        ? (document.getElementById('inputPodcastScript')?.value?.trim() || null)
        : null;
      
      const statusBox = document.getElementById('newJobStatus');
      const submitBtn = document.getElementById('submitJobBtn');

      statusBox.className = 'p-3 rounded-xl bg-zinc-950 border border-zinc-800 text-xs flex items-center space-x-2 text-zinc-300';
      statusBox.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin text-emerald-400 shrink-0"></i><span>Enqueuing speech generation in background...</span>';
      lucide.createIcons();
      submitBtn.disabled = true;

      try {
        const resp = await fetch('/api/jobs', {
          method: 'POST',
          headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ text, persona, run_judge, voice_customization, speed, podcast_script })
        });
        const data = await resp.json();
        if (!resp.ok) {
          let errMsg = 'Job creation failed';
          if (Array.isArray(data.detail)) {
            errMsg = data.detail.map(d => `${d.loc ? d.loc.slice(1).join('.') + ': ' : ''}${d.msg}`).join(', ');
          } else if (typeof data.detail === 'string') {
            errMsg = data.detail;
          } else if (data.message) {
            errMsg = data.message;
          }
          throw new Error(errMsg);
        }

        // Immediately update in-memory job directory and trigger polling
        if (data.job) {
          const existingIdx = ALL_JOBS.findIndex(j => j.job_id === data.job.job_id);
          if (existingIdx !== -1) {
            ALL_JOBS[existingIdx] = data.job;
          } else {
            ALL_JOBS.unshift(data.job);
          }
          filterJobs(false);
          checkAndStartPolling();
        }

        closeNewJobModal();
        submitBtn.disabled = false;
        loadStats();
        await openJobDetail(data.job_id, data.job);

      } catch (err) {
        statusBox.className = 'p-3 rounded-xl bg-rose-950/40 border border-rose-800/60 text-xs flex items-center space-x-2 text-rose-300';
        statusBox.innerHTML = `<i data-lucide="alert-circle" class="w-4 h-4 text-rose-400 shrink-0"></i><span>Error: ${err.message}</span>`;
        lucide.createIcons();
        submitBtn.disabled = false;
      }
    }

    // Bulk Process Modal Handlers
    function openBulkJobModal() {
      const statusBox = document.getElementById('bulkJobStatus');
      if (statusBox) {
        statusBox.className = 'hidden p-3 rounded-xl bg-zinc-950 border border-zinc-800 text-xs flex items-center space-x-2';
        statusBox.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin text-teal-400"></i><span id="bulkJobStatusText" class="text-zinc-300">Validating & enqueuing URLs...</span>';
      }
      document.getElementById('bulkJobModal').classList.remove('hidden');
      updateBulkUrlStats();
      lucide.createIcons();
    }

    function closeBulkJobModal() {
      document.getElementById('bulkJobModal').classList.add('hidden');
      const statusBox = document.getElementById('bulkJobStatus');
      if (statusBox) {
        statusBox.className = 'hidden p-3 rounded-xl bg-zinc-950 border border-zinc-800 text-xs flex items-center space-x-2';
        statusBox.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin text-teal-400"></i><span id="bulkJobStatusText" class="text-zinc-300">Validating & enqueuing URLs...</span>';
      }
      const textEl = document.getElementById('inputBulkUrls');
      if (textEl) textEl.value = '';
      const voiceInput = document.getElementById('inputBulkVoiceCustomization');
      if (voiceInput) voiceInput.value = '';
      const bulkSpeedSlider = document.getElementById('inputBulkSpeed');
      if (bulkSpeedSlider) {
        bulkSpeedSlider.value = '1.0';
        updateBulkSpeedDisplay('1.0');
      }
    }

    function updateBulkUrlStats() {
      const text = document.getElementById('inputBulkUrls').value;
      const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
      const countEl = document.getElementById('bulkUrlStats');
      const warnEl = document.getElementById('bulkUrlValidationWarning');
      const warnText = document.getElementById('bulkUrlValidationText');

      if (lines.length === 0) {
        countEl.textContent = '0 URLs entered';
        warnEl.classList.add('hidden');
        return;
      }

      let invalidCount = 0;
      for (const line of lines) {
        if (!line.startsWith('http://') && !line.startsWith('https://')) {
          invalidCount++;
        } else {
          try {
            const u = new URL(line);
            if (!u.hostname.includes('.')) invalidCount++;
          } catch(e) {
            invalidCount++;
          }
        }
      }

      const validCount = lines.length - invalidCount;
      countEl.textContent = `${lines.length} URL${lines.length === 1 ? '' : 's'} (${validCount} valid)`;

      if (invalidCount > 0) {
        warnText.textContent = `${invalidCount} line${invalidCount === 1 ? '' : 's'} not a valid HTTP/HTTPS URL`;
        warnEl.classList.remove('hidden');
      } else {
        warnEl.classList.add('hidden');
      }
    }

    function loadSampleUrls() {
      document.getElementById('inputBulkUrls').value = [
        'https://www.federalreserve.gov/newsevents/pressreleases/monetary20240918a.htm',
        'https://www.fdic.gov/news/press-releases/2024/pr24012.html',
        'https://en.wikipedia.org/wiki/Certificate_of_deposit'
      ].join('\n');
      updateBulkUrlStats();
      lucide.createIcons();
    }

    async function submitBulkJobs(e) {
      e.preventDefault();
      const text = document.getElementById('inputBulkUrls').value;
      const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
      const persona = document.getElementById('inputBulkPersona').value;
      const voice_customization = document.getElementById('inputBulkVoiceCustomization')?.value?.trim() || null;
      const speed = parseFloat(document.getElementById('inputBulkSpeed')?.value || '1.0');
      const run_judge = document.getElementById('inputBulkRunJudge').checked;

      const statusBox = document.getElementById('bulkJobStatus');
      const submitBtn = document.getElementById('submitBulkJobBtn');

      if (lines.length === 0) {
        alert('Please enter at least one URL.');
        return;
      }

      statusBox.className = 'p-3 rounded-xl bg-zinc-950 border border-zinc-800 text-xs flex items-center space-x-2 text-zinc-300';
      statusBox.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin text-teal-400 shrink-0"></i><span>Validating & enqueuing ${lines.length} URLs for sequential processing...</span>`;
      lucide.createIcons();
      submitBtn.disabled = true;

      try {
        const resp = await fetch('/api/jobs/bulk', {
          method: 'POST',
          headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ urls: lines, persona, voice_customization, speed, run_judge })
        });
        const data = await resp.json();
        if (!resp.ok) {
          let errMsg = 'Bulk processing failed to enqueue';
          if (Array.isArray(data.detail)) {
            errMsg = data.detail.map(d => `${d.loc ? d.loc.slice(1).join('.') + ': ' : ''}${d.msg}`).join(', ');
          } else if (typeof data.detail === 'string') {
            errMsg = data.detail;
          } else if (data.message) {
            errMsg = data.message;
          }
          throw new Error(errMsg);
        }

        // Immediately update in-memory job directory and trigger polling
        if (data.jobs && data.jobs.length > 0) {
          for (let i = data.jobs.length - 1; i >= 0; i--) {
            const jb = data.jobs[i];
            const existingIdx = ALL_JOBS.findIndex(j => j.job_id === jb.job_id);
            if (existingIdx !== -1) {
              ALL_JOBS[existingIdx] = jb;
            } else {
              ALL_JOBS.unshift(jb);
            }
          }
          filterJobs(false);
          checkAndStartPolling();
        }

        closeBulkJobModal();
        submitBtn.disabled = false;
        loadStats();
        if (data.jobs && data.jobs.length > 0) {
          await openJobDetail(data.jobs[0].job_id, data.jobs[0]);
        }

      } catch (err) {
        statusBox.className = 'p-3 rounded-xl bg-rose-950/40 border border-rose-800/60 text-xs flex items-center space-x-2 text-rose-300';
        statusBox.innerHTML = `<i data-lucide="alert-circle" class="w-4 h-4 text-rose-400 shrink-0"></i><span>Error: ${err.message}</span>`;
        lucide.createIcons();
        submitBtn.disabled = false;
      }
    }

