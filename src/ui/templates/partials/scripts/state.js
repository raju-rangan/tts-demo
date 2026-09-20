    let AUTH_TOKEN = localStorage.getItem('apex_tts_token') || null;
    let CURRENT_PERSONA = localStorage.getItem('apex_tts_persona') || 'creator';
    let ALL_JOBS = [];
    let FILTERED_JOBS = [];
    let CURRENT_PAGE = 1;
    let PAGE_SIZE = 10;
    let CURRENT_JOB = null;
    let AUTH_CONFIG = null;
    let FIREBASE_APP = null;
    let GLOBAL_STATS = null;
    let AUDITOR_SUB_VIEW = 'dashboard';
    let chartInstances = {};

    const IS_LOCALHOST = ['localhost', '127.0.0.1', '0.0.0.0'].includes(window.location.hostname) || window.location.hostname.endsWith('.local');

    function getAuthHeaders(extra = {}) {
      const token = AUTH_TOKEN || (IS_LOCALHOST ? 'local-dev-token' : '');
      const h = {
        'Authorization': `Bearer ${token}`,
        'X-Apex-Persona': CURRENT_PERSONA
      };
      return Object.assign(h, extra);
    }

    let COMPLIANCE_FILTER = 'all';

