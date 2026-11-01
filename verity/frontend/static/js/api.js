/*
 * Verity — shared frontend API client.
 * Loaded on every page. Wraps fetch() with:
 *   - JWT attach/detach (localStorage)
 *   - JSON body encode / decode
 *   - consistent error messages (never a silent failure or blank page)
 */
window.Verity = (function () {
  const TOKEN_KEY = 'verity_token';
  const USER_KEY = 'verity_user';

  function getToken() { return localStorage.getItem(TOKEN_KEY); }
  function setToken(token) { localStorage.setItem(TOKEN_KEY, token); }
  function clearToken() { localStorage.removeItem(TOKEN_KEY); }

  function getUser() {
    try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); }
    catch (e) { return null; }
  }
  function setUser(user) { localStorage.setItem(USER_KEY, JSON.stringify(user)); }

  function logout() {
    clearToken();
    localStorage.removeItem(USER_KEY);
    window.location.href = '/auth';
  }

  /**
   * api(path, { method, body, auth, isForm })
   * - body: plain object -> sent as JSON, unless isForm is true (FormData passthrough)
   * - auth: true by default; attaches "Authorization: Bearer <token>"
   * Throws an Error with a human-readable .message on any non-2xx response
   * or network failure, so callers can just try/catch and display it.
   */
  async function api(path, options = {}) {
    const { method = 'GET', body = null, auth = true, isForm = false } = options;
    const headers = {};
    if (!isForm && body !== null) headers['Content-Type'] = 'application/json';
    if (auth) {
      const token = getToken();
      if (!token) {
        window.location.href = '/auth';
        throw new Error('Not authenticated.');
      }
      headers['Authorization'] = `Bearer ${token}`;
    }

    let response;
    try {
      response = await fetch(path, {
        method,
        headers,
        body: body === null ? undefined : (isForm ? body : JSON.stringify(body)),
      });
    } catch (networkErr) {
      throw new Error('Could not reach the server. Check your connection and try again.');
    }

    let data = null;
    const text = await response.text();
    if (text) {
      try { data = JSON.parse(text); }
      catch (parseErr) { data = null; }
    }

    if (response.status === 401 && auth) {
      // Session expired / invalid — send back to login rather than
      // showing a confusing dead-end screen.
      clearToken();
      window.location.href = '/auth';
      throw new Error('Your session has expired. Please log in again.');
    }

    if (!response.ok) {
      const message = (data && data.error) || `Request failed (HTTP ${response.status}).`;
      throw new Error(message);
    }

    return data;
  }

  function requireAuth() {
    if (!getToken()) {
      window.location.href = '/auth';
      return false;
    }
    return true;
  }

  function timeAgo(isoString) {
    if (!isoString) return 'Unknown date';
    const date = new Date(isoString);
    const diffMs = Date.now() - date.getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 30) return `${days}d ago`;
    return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  }

  function formatDate(isoString) {
    if (!isoString) return 'Unknown date';
    const date = new Date(isoString);
    return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
  }

  return { getToken, setToken, clearToken, getUser, setUser, logout, api, requireAuth, timeAgo, formatDate, escapeHtml };
})();
