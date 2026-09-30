/**
 * The single place the app talks to the backend.
 *
 * Every response uses the envelope { status, data, message }. A 401 means the
 * session has gone — the caller is told, and App.jsx drops back to the login
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

  const response = await fetch(`/api${path}`, {
    method,
    signal,
    credentials: 'same-origin',
    headers: isForm || body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: isForm ? body : body === undefined ? undefined : JSON.stringify(body),
  });

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

export const api = {
  session: () => request('/session'),
  login: (username, password) => request('/login', { method: 'POST', body: { username, password } }),
  logout: () => request('/logout', { method: 'POST' }),

  schedule: (filters, signal) => request(`/schedule?${new URLSearchParams(filters)}`, { signal }),
  forwarders: () => request('/forwarders'),

  bookings: () => request('/bookings'),
  enquiry: (payload) => request('/enquiry', { method: 'POST', body: payload }),
  saveQuotes: (ref, quotes) => request(`/bookings/${encodeURIComponent(ref)}/quotes`, { method: 'POST', body: { quotes } }),
  chooseForwarder: (ref, forwarderId) => request(`/bookings/${encodeURIComponent(ref)}/choose`, { method: 'POST', body: { forwarder_id: forwarderId } }),
  sendDocuments: (ref, formData) => request(`/bookings/${encodeURIComponent(ref)}/documents`, { method: 'POST', body: formData }),

  shareEmail: (payload) => request('/share/email', { method: 'POST', body: payload }),
  shareWhatsApp: (payload) => request('/share/whatsapp', { method: 'POST', body: payload }),

  waContacts: () => request('/wa-contacts'),
  saveWaContact: (payload) => request('/wa-contacts', { method: 'POST', body: payload }),
};

export default api;
