/**
 * The single place the app talks to the backend.
 *
 * Every response uses the envelope { status, data, message }. A 401 means there
 * is no live session — the caller is told, and App.jsx drops back to the login
 * screen rather than showing an empty list that looks like "no results".
 */

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }

  get isUnauthorised() {
    return this.status === 401;
  }
}

async function request(path, { method = 'GET', body, signal } = {}) {
  const isForm = body instanceof FormData;

  let response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      signal,
      // The session cookie must ride along on every call, including the very
      // first /me check.
      credentials: 'include',
      headers: isForm || body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: isForm ? body : body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (cause) {
    // Network down, server not running, request aborted. Distinct from "the
    // server answered and said no" — the user sees a different message.
    if (cause.name === 'AbortError') throw cause;
    throw new ApiError('Cannot reach the server. Check your connection.', 0);
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // A non-JSON body means something upstream went wrong, not a valid answer.
  }

  if (!response.ok || !payload || payload.status !== 'ok') {
    const message = (payload && payload.message) || 'Something went wrong. Please try again.';
    throw new ApiError(message, response.status);
  }

  return payload.data;
}

/** Drop empty values so the server sees an absent filter, not a blank one. */
function queryString(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== '') search.set(key, value);
  }
  const query = search.toString();
  return query ? `?${query}` : '';
}

export const api = {
  // --- auth ---
  me: (signal) => request('/me', { signal }),
  login: (username, password) => request('/login', { method: 'POST', body: { username, password } }),
  logout: () => request('/logout', { method: 'POST' }),

  // --- finder ---
  schedule: (filters, signal) => request(`/schedule${queryString(filters)}`, { signal }),
  scheduleFilters: (country, signal) =>
    request(`/schedule/filters${queryString({ country })}`, { signal }),

  // --- users (admin only; the server answers 403 for anyone else) ---
  users: (signal) => request('/users', { signal }),
  createUser: (payload) => request('/users', { method: 'POST', body: payload }),
  removeUser: (username) => request(`/users/${encodeURIComponent(username)}`, { method: 'DELETE' }),

  // --- everything below arrives with its own feature branch ---
  forwarders: () => request('/forwarders'),
  enquiryOrigin: () => request('/enquiry-origin'),

  bookings: (signal) => request('/bookings', { signal }),
  enquiry: (payload) => request('/enquiry', { method: 'POST', body: payload }),
  saveQuotes: (ref, quotes) => request(`/bookings/${encodeURIComponent(ref)}/quotes`, { method: 'POST', body: { quotes } }),
  chooseForwarder: (ref, forwarderId) => request(`/bookings/${encodeURIComponent(ref)}/choose`, { method: 'POST', body: { forwarder_id: forwarderId } }),
  sendDocuments: (ref, formData) => request(`/bookings/${encodeURIComponent(ref)}/documents`, { method: 'POST', body: formData }),

  /** The PDF the shares attach, for the current filters — a link to open, not a fetch. */
  sharePdfUrl: (filters) => `/api/share/pdf${queryString(filters)}`,
  shareEmail: (payload) => request('/share/email', { method: 'POST', body: payload }),
  shareWhatsApp: (payload) => request('/share/whatsapp', { method: 'POST', body: payload }),

  waContacts: () => request('/wa-contacts'),
  saveWaContact: (payload) => request('/wa-contacts', { method: 'POST', body: payload }),
};

export default api;
