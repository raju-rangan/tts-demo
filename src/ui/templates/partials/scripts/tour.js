    // ================= INTERACTIVE ONBOARDING TOUR ENGINE =================
    let TOUR_DRIVER_INSTANCE = null;

    async function checkAndPromptTour() {
      if (!AUTH_TOKEN) return;
      try {
        const personaParam = encodeURIComponent(CURRENT_PERSONA || 'creator');
        const resp = await fetch(`/api/user/tour-status?persona=${personaParam}`, {
          headers: getAuthHeaders()
        });
        if (resp.ok) {
          const data = await resp.json();
          // If user has not yet completed or dismissed the tour for this persona, auto-launch
          if (data && data.has_seen_tour === false) {
            setTimeout(() => {
              // Ensure we are still on this persona and app is visible
              if (!document.getElementById('appSection')?.classList.contains('hidden')) {
                startGuidedTour(false);
              }
            }, 800);
          }
        }
      } catch (err) {
        console.warn("Could not check onboarding tour status:", err);
      }
    }

    async function recordTourDismissal() {
      if (!AUTH_TOKEN) return;
      try {
        await fetch('/api/user/tour-dismiss', {
          method: 'POST',
          headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ persona: CURRENT_PERSONA })
        });
        console.log(`✓ Tour dismissal recorded in database for persona '${CURRENT_PERSONA}'`);
      } catch (err) {
        console.warn("Failed to record tour dismissal:", err);
      }
    }

    async function resetTourStatus() {
      if (!AUTH_TOKEN) return;
      try {
        await fetch('/api/user/tour-reset', {
          method: 'POST',
          headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ persona: CURRENT_PERSONA })
        });
        console.log(`✓ Tour status reset in database for persona '${CURRENT_PERSONA}'`);
        startGuidedTour(true);
      } catch (err) {
        console.warn("Failed to reset tour status:", err);
      }
    }

    async function resetAllTours() {
      if (!AUTH_TOKEN) return;
      try {
        await fetch('/api/user/tour-reset-all', {
          method: 'POST',
          headers: getAuthHeaders()
        });
        console.log("✓ All onboarding tour records reset across database");
        startGuidedTour(true);
      } catch (err) {
        console.warn("Failed to reset all tour records:", err);
      }
    }

    function startGuidedTour(force = false) {
      if (!window.driver || !window.driver.js || !window.driver.js.driver) {
        console.warn("Driver.js library not loaded yet.");
        return;
      }

      // Check active persona to display tailored walkthrough
      const isAuditor = CURRENT_PERSONA === 'auditor';

      const creatorSteps = [
        {
          element: '#btnSwitchPersona',
          popover: {
            title: '1. Workspace Persona Hub',
            description: 'Switch seamlessly between <strong>Sarah Jenkins</strong> (Creator Mode: voice generation & bulk ingestion) and <strong>David Chen</strong> (Auditor Mode: multimodal quality gates & FinOps governance).',
            side: 'bottom',
            align: 'start'
          }
        },
        {
          element: '#btnNavNewJob',
          popover: {
            title: '2. Voice Synthesis Engine',
            description: 'Generate studio-grade spoken disclosures powered by <strong>Gemini 3.1 Flash TTS preview</strong>. Configure natural speaking rates, emotional inflections, and pronunciation overrides.',
            side: 'bottom',
            align: 'end'
          }
        },
        {
          element: '#btnNavBulk',
          popover: {
            title: '3. Bulk Article Extraction',
            description: 'Synthesize multiple press releases or regulatory articles in batch. Gemini extracts clean text and schedules sequential audio production.',
            side: 'bottom',
            align: 'end'
          }
        },
        {
          element: '#creatorStudioSection',
          popover: {
            title: '4. Enterprise Audio Studio',
            description: 'Monitor overall throughput: total audio generated, average multimodal quality score, and real-time FinOps cost tracking across all runs.',
            side: 'bottom',
            align: 'center'
          }
        },
        {
          element: '#jobDirectorySection',
          popover: {
            title: '5. Audio Registry & Playback',
            description: 'Inspect generated jobs. Stream 24kHz audio, review transcripts, examine token breakdowns, and inspect <strong>Gemini 3.8 Flash Multimodal Quality Scorecards</strong>.',
            side: 'top',
            align: 'center'
          }
        },
        {
          element: '#btnGuidedTour',
          popover: {
            title: '6. Tour Always Accessible',
            description: 'You are all set! Click this <strong>Guided Tour</strong> compass button anytime to replay this interactive walkthrough.',
            side: 'bottom',
            align: 'end'
          }
        }
      ];

      const auditorSteps = [
        {
          element: '#btnSwitchPersona',
          popover: {
            title: '1. Workspace Persona Hub',
            description: 'Switch between <strong>David Chen</strong> (Senior Regulatory Compliance Analyst) and <strong>Sarah Jenkins</strong> (Senior Digital Communications Specialist).',
            side: 'bottom',
            align: 'start'
          }
        },
        {
          element: '#auditorSubNav',
          popover: {
            title: '2. Executive Dashboard vs. Registry',
            description: 'Toggle between the high-level <strong>Executive Governance Dashboard</strong> and the granular <strong>Disclosure Audio Registry</strong>.',
            side: 'bottom',
            align: 'start'
          }
        },
        {
          element: '#btnNavFinOps',
          popover: {
            title: '3. FinOps & Governance Drawer',
            description: 'Inspect live unit economics, Gemini TTS vs. Judge cost breakdowns, BigQuery / Firestore sync status, and SLA compliance metrics.',
            side: 'bottom',
            align: 'end'
          }
        },
        {
          element: '#auditorFullDashboard',
          popover: {
            title: '4. Multimodal AI Quality Gates',
            description: 'Audit compliance scores across 5 financial personas, evaluate rubric adherence (Truth in Lending, script adherence), and review flagged disclosures.',
            side: 'top',
            align: 'center'
          }
        },
        {
          element: '#btnGuidedTour',
          popover: {
            title: '5. Replay Tour Anytime',
            description: 'Need a refresher? Click <strong>Guided Tour</strong> anytime to walk through these compliance and governance controls.',
            side: 'bottom',
            align: 'end'
          }
        }
      ];

      const steps = isAuditor ? auditorSteps : creatorSteps;

      // Filter out any elements not currently in the DOM or hidden
      const validSteps = steps.filter(s => {
        const el = document.querySelector(s.element);
        return el && !el.classList.contains('hidden') && el.offsetParent !== null;
