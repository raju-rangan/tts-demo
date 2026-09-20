    function setComplianceFilter(filterVal) {
      COMPLIANCE_FILTER = filterVal;
      const tabAll = document.getElementById('filterTabAll');
      const tabComp = document.getElementById('filterTabCompliant');
      const tabFlag = document.getElementById('filterTabFlagged');

      const activeCls = "px-3 py-1 rounded-lg bg-purple-500/20 text-purple-300 border border-purple-500/30 transition font-semibold";
      const inactiveCls = "px-3 py-1 rounded-lg text-zinc-400 hover:text-zinc-200 border border-transparent transition";

      if (tabAll) tabAll.className = filterVal === 'all' ? activeCls : inactiveCls;
      if (tabComp) tabComp.className = filterVal === 'compliant' ? activeCls : inactiveCls;
      if (tabFlag) tabFlag.className = filterVal === 'flagged' ? activeCls : inactiveCls;

      filterJobs(true);
    }

    async function selectPersona(personaType) {
      CURRENT_PERSONA = personaType;
      localStorage.setItem('apex_tts_persona', personaType);
      updatePersonaUI();
      if (AUTH_TOKEN) {
        try {
          const resp = await fetch('/api/auth/me', { headers: getAuthHeaders() });
          if (resp.ok) {
            const data = await resp.json();
            setUserHeader(data.user);
          }
        } catch (e) {
          console.warn("Could not refresh user after persona change:", e);
        }
      }
      checkAndPromptTour();
    }

    function updatePersonaUI() {
      const creatorSection = document.getElementById('creatorStudioSection');
      const auditorSection = document.getElementById('auditorConsoleSection');
      const btnNavNewJob = document.getElementById('btnNavNewJob');
      const btnNavBulk = document.getElementById('btnNavBulk');
      const btnNavFinOps = document.getElementById('btnNavFinOps');
      const complianceTabs = document.getElementById('complianceFilterTabs');
      const tableTitle = document.getElementById('tableTitle');
      const tableSubtitle = document.getElementById('tableSubtitle');
      const jobDirectory = document.getElementById('jobDirectorySection');

      if (CURRENT_PERSONA === 'auditor') {
        if (creatorSection) creatorSection.classList.add('hidden');
        if (auditorSection) auditorSection.classList.remove('hidden');
        if (btnNavNewJob) btnNavNewJob.classList.add('hidden');
        if (btnNavBulk) btnNavBulk.classList.add('hidden');
        if (btnNavFinOps) btnNavFinOps.classList.remove('hidden');
        if (complianceTabs) complianceTabs.classList.remove('hidden');
        if (tableTitle) tableTitle.textContent = "Regulatory Compliance & Disclosure Audio Registry";
        if (tableSubtitle) tableSubtitle.textContent = "Auditing Gemini 3.8 Flash Multimodal quality gate, disclosure clarity, and regulatory adherence.";
        switchAuditorSubView(AUDITOR_SUB_VIEW || 'dashboard');
      } else {
        if (creatorSection) creatorSection.classList.remove('hidden');
        if (auditorSection) auditorSection.classList.add('hidden');
        if (btnNavNewJob) btnNavNewJob.classList.remove('hidden');
        if (btnNavBulk) btnNavBulk.classList.remove('hidden');
        if (btnNavFinOps) btnNavFinOps.classList.add('hidden');
        if (complianceTabs) complianceTabs.classList.add('hidden');
        if (tableTitle) tableTitle.textContent = "Synthesis & Quality Audit Job History";
        if (tableSubtitle) tableSubtitle.textContent = "Click on any job to inspect full transcripts, GCS storage paths, token metrics, and diagnostic scorecards.";
        if (jobDirectory) jobDirectory.classList.remove('hidden');
      }
      lucide.createIcons();
    }

    // Initialize GCIP Authentication
    async function initAuthSystem() {
      try {
        const resp = await fetch('/api/auth/config');
        AUTH_CONFIG = await resp.json();

        if (AUTH_CONFIG.project_id && document.getElementById('navProjectId')) {
          document.getElementById('navProjectId').textContent = AUTH_CONFIG.project_id;
        }

        // Initialize Firebase SDK if API Key is configured
        if (AUTH_CONFIG.api_key && AUTH_CONFIG.project_id && window.firebase) {
          if (!firebase.apps.length) {
            FIREBASE_APP = firebase.initializeApp({
              apiKey: AUTH_CONFIG.api_key,
              authDomain: AUTH_CONFIG.auth_domain,
              projectId: AUTH_CONFIG.project_id
            });
          } else {
            FIREBASE_APP = firebase.app();
          }

          // Listen for ID token lifecycle updates & auto-refresh
          firebase.auth().onIdTokenChanged(async (user) => {
            if (user) {
              try {
                const token = await user.getIdToken();
                AUTH_TOKEN = token;
                localStorage.setItem('apex_tts_token', token);
              } catch (te) {
                console.warn("Could not auto-refresh ID token:", te);
              }
            }
          });
        }
      } catch (err) {
        console.warn("Could not load auth configuration:", err);
      }

      // Initialize Official Google Identity Services (GIS) Web SDK
      setupGoogleIdentityServices();
    }

    document.addEventListener('DOMContentLoaded', async () => {
      lucide.createIcons();
      updatePersonaUI();
      await initAuthSystem();

      // Automatic Localhost Bypass
      if (IS_LOCALHOST) {
        const badge = document.getElementById('navLocalDevBadge');
        if (badge) {
          badge.classList.remove('hidden');
          badge.classList.add('inline-flex');
        }
        const bypassCard = document.getElementById('localBypassCard');
        if (bypassCard) {
          bypassCard.classList.remove('hidden');
        }

        if (!AUTH_TOKEN || AUTH_TOKEN === 'null' || AUTH_TOKEN === 'undefined') {
          AUTH_TOKEN = 'local-dev-token';
          localStorage.setItem('apex_tts_token', AUTH_TOKEN);
        }

        const storedPersona = localStorage.getItem('apex_tts_persona');
        const activePersona = storedPersona || CURRENT_PERSONA || 'creator';
        const defaultUser = {
          email: 'local-dev@apexbank.com',
          google_email: 'local-dev@apexbank.com',
          name: activePersona === 'auditor' ? 'David Chen' : 'Sarah Jenkins',
          role: activePersona === 'auditor' ? 'Senior Regulatory Compliance Analyst' : 'Senior Digital Communications Specialist',
          department: activePersona === 'auditor' ? 'Communications Compliance & Disclosure Oversight' : 'Digital Wealth Communications & Publishing',
          persona_type: activePersona,
          avatar: activePersona === 'auditor' ? '/static/avatars/auditor_david.jpg' : '/static/avatars/creator_sarah.jpg'
        };
        setUserHeader(defaultUser);

        if (storedPersona) {
          CURRENT_PERSONA = storedPersona;
          showApp();
        } else {
          showProfileSelect('local-dev@apexbank.com');
        }
        return;
      }

      const params = new URLSearchParams(window.location.search);
      const view = params.get('view');
      if (view && AUTH_CONFIG?.enable_demo_auth) {
        try {
          const resp = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: 'admin@apexbank.com', password: 'demo1234' })
          });
          const data = await resp.json();
          AUTH_TOKEN = data.token;
          localStorage.setItem('apex_tts_token', AUTH_TOKEN);
          setUserHeader(data.user);
          showApp();

          if (view === 'new_job') {
            openNewJobModal();
            loadSampleText();
          } else if (view === 'bulk') {
            openBulkJobModal();
            loadSampleUrls();
          } else if (view === 'job_detail' || view === 'scorecard' || view === 'finops') {
            await loadJobs();
            if (ALL_JOBS.length > 0) {
              const targetJob = ALL_JOBS.find(j => j.status === 'COMPLETED' && j.overall_score) || ALL_JOBS[0];
              await openJobDetail(targetJob.job_id);
              if (view === 'scorecard') {
                const scrollable = document.querySelector('#jobDetailModal .overflow-y-auto');
                if (scrollable) scrollable.scrollTop = 580;
              } else if (view === 'finops') {
                const scrollable = document.querySelector('#jobDetailModal .overflow-y-auto');
                if (scrollable) scrollable.scrollTop = 140;
              }
            }
          }
          return;
        } catch (e) {
          console.error('Deep link initialization failed', e);
        }
      }

      if (AUTH_TOKEN) {
        verifySession();
      } else {
        showLogin();
      }
    });

    // Screen Navigation Handlers
    function showLogin() {
      if (IS_LOCALHOST) {
        const bypassCard = document.getElementById('localBypassCard');
        if (bypassCard) bypassCard.classList.remove('hidden');
      }
      document.getElementById('loginSection').classList.remove('hidden');
      document.getElementById('profileSelectSection')?.classList.add('hidden');
      document.getElementById('appSection').classList.add('hidden');
    }

    function bypassAuthLocal() {
      AUTH_TOKEN = 'local-dev-token';
      localStorage.setItem('apex_tts_token', AUTH_TOKEN);
      const storedPersona = localStorage.getItem('apex_tts_persona');
      const activePersona = storedPersona || CURRENT_PERSONA || 'creator';
      const defaultUser = {
        email: 'local-dev@apexbank.com',
        google_email: 'local-dev@apexbank.com',
        name: activePersona === 'auditor' ? 'David Chen' : 'Sarah Jenkins',
        role: activePersona === 'auditor' ? 'Senior Regulatory Compliance Analyst' : 'Senior Digital Communications Specialist',
        department: activePersona === 'auditor' ? 'Communications Compliance & Disclosure Oversight' : 'Digital Wealth Communications & Publishing',
        persona_type: activePersona,
        avatar: activePersona === 'auditor' ? '/static/avatars/auditor_david.jpg' : '/static/avatars/creator_sarah.jpg'
      };
      setUserHeader(defaultUser);
      if (storedPersona) {
        showApp();
      } else {
        showProfileSelect('local-dev@apexbank.com');
      }
    }

    function showProfileSelect(email) {
      document.getElementById('loginSection').classList.add('hidden');
      document.getElementById('appSection').classList.add('hidden');
      const gateEmailEl = document.getElementById('gateUserEmail');
      const activeEmail = email || document.getElementById('userGoogleEmail')?.textContent || gateEmailEl?.textContent;
      if (gateEmailEl && activeEmail) gateEmailEl.textContent = activeEmail;
      const selectSection = document.getElementById('profileSelectSection');
      if (selectSection) {
        selectSection.classList.remove('hidden');
        lucide.createIcons();
      }
    }

    async function choosePersona(personaType) {
      CURRENT_PERSONA = personaType;
      localStorage.setItem('apex_tts_persona', personaType);
      updatePersonaUI();
      showApp();
      if (AUTH_TOKEN) {
        try {
          const resp = await fetch('/api/auth/me', { headers: getAuthHeaders() });
          if (resp.ok) {
            const data = await resp.json();
            setUserHeader(data.user);
          }
        } catch (e) {
          console.warn("Could not refresh user header:", e);
        }
      }
    }

    function showApp() {
      document.getElementById('loginSection').classList.add('hidden');
      document.getElementById('profileSelectSection')?.classList.add('hidden');
      document.getElementById('appSection').classList.remove('hidden');
      updatePersonaUI();
      loadStats();
      loadJobs();
      checkAndPromptTour();
    }

    // Google Identity Services (GIS) Official Client Initialization
    function setupGoogleIdentityServices() {
      if (IS_LOCALHOST) {
        return; // Skip GIS client on localhost to avoid OAuth origin mismatch
      }
      const clientId = AUTH_CONFIG?.google_client_id;
      if (!clientId) {
        console.warn("Google Client ID not configured in auth config.");
        return;
      }

      if (window.google?.accounts?.id) {
        try {
          google.accounts.id.initialize({
            client_id: clientId,
            callback: handleGoogleCredentialResponse,
            auto_select: false,
            cancel_on_tap_outside: true
          });

          const btnContainer = document.getElementById('googleSignInButton');
          if (btnContainer) {
            btnContainer.innerHTML = '';
            google.accounts.id.renderButton(btnContainer, {
              type: 'standard',
              theme: 'outline',
              size: 'large',
              text: 'signin_with',
              shape: 'pill',
              logo_alignment: 'left',
              width: 320
            });
          }
        } catch (e) {
          console.warn("Error initializing Google Identity Services:", e);
        }
      } else {
        // GSI script may still be loading asynchronously
        setTimeout(setupGoogleIdentityServices, 250);
      }
    }

    async function handleGoogleCredentialResponse(response) {
      const errBox = document.getElementById('loginError');
      if (errBox) errBox.classList.add('hidden');

      if (!response || !response.credential) {
        if (errBox) {
          errBox.textContent = "Google Sign-In was cancelled or failed to return a credential.";
          errBox.classList.remove('hidden');
        }
        return;
      }

      try {
        const resp = await fetch('/api/auth/google-login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ credential: response.credential })
        });
        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.detail || 'Google sign-in authorization failed.');
        }

        AUTH_TOKEN = data.token;
        localStorage.setItem('apex_tts_token', data.token);
        showProfileSelect(data.user.google_email || data.user.email);
      } catch (err) {
        console.error("Google sign-in error:", err);
        if (errBox) {
          errBox.textContent = err.message || "Failed to authenticate Google identity.";
          errBox.classList.remove('hidden');
        }
      }
    }

    async function verifySession() {
      const errBox = document.getElementById('loginError');
      if (IS_LOCALHOST) {
        try {
          const resp = await fetch('/api/auth/me', {
            headers: getAuthHeaders()
          });
          if (resp.ok) {
            const data = await resp.json();
            setUserHeader(data.user);
          }
        } catch (e) {
          console.warn("Localhost session check error:", e);
        }
        const storedPersona = localStorage.getItem('apex_tts_persona');
        if (storedPersona) {
          showApp();
        } else {
          showProfileSelect('local-dev@apexbank.com');
        }
        return;
      }

      try {
        const resp = await fetch('/api/auth/me', {
          headers: getAuthHeaders()
        });
        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          throw new Error(errData.detail || 'Session expired');
        }
        const data = await resp.json();
        setUserHeader(data.user);
        
        const storedPersona = localStorage.getItem('apex_tts_persona');
        if (storedPersona) {
          showApp();
        } else {
          showProfileSelect(data.user.google_email || data.user.email);
        }
      } catch (err) {
        AUTH_TOKEN = null;
        localStorage.removeItem('apex_tts_token');
        localStorage.removeItem('apex_tts_persona');
        if (errBox && err.message && err.message !== 'Session expired') {
          errBox.textContent = err.message;
          errBox.classList.remove('hidden');
        }
        showLogin();
      }
    }

    function setUserHeader(user) {
      document.getElementById('userName').textContent = user.name || 'Sarah Jenkins';
      document.getElementById('userRole').textContent = user.role || 'Senior Digital Communications Specialist';
      
      const emailEl = document.getElementById('userGoogleEmail');
      const googleEmail = user.google_email || (user.email && !user.email.includes('apexbank.com') ? user.email : null);
      if (emailEl) {
        if (googleEmail) {
          emailEl.textContent = googleEmail;
          emailEl.classList.remove('hidden');
          emailEl.title = `Authenticated Google Account: ${googleEmail}`;
        } else {
          emailEl.classList.add('hidden');
        }
      }

      const avatarEl = document.getElementById('userAvatar');
      const avatarSrc = user.avatar || (user.persona_type === 'auditor' ? '/static/avatars/auditor_david.jpg' : '/static/avatars/creator_sarah.jpg');
      avatarEl.innerHTML = `<img src="${avatarSrc}" alt="${user.name}" class="w-full h-full object-cover rounded-full shadow-sm">`;
    }

    async function handleLogout() {
      if (window.firebase && firebase.apps?.length && firebase.auth().currentUser) {
        try {
          await firebase.auth().signOut();
        } catch (e) {
          console.warn("Firebase sign out error:", e);
        }
      }
      AUTH_TOKEN = null;
      localStorage.removeItem('apex_tts_token');
      localStorage.removeItem('apex_tts_persona');
      if (IS_LOCALHOST) {
        showProfileSelect('local-dev@apexbank.com');
      } else {
        showLogin();
      }
    }

    // Analytics Stats
