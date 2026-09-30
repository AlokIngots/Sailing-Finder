/*
  PLACEHOLDER — the real app.js is the behaviour from reference/Index.html with
  its data layer swapped, which has not been supplied yet. Nothing has been
  invented here.

  The swap, when it happens:
    google.script.run.withSuccessHandler(fn).getSchedule()   ->  GET  /api/schedule
    google.script.run...sendEnquiry(payload)                 ->  POST /api/enquiry
    google.script.run...saveQuotes(ref, quotes)              ->  POST /api/bookings/:ref/quotes
    google.script.run...chooseForwarder(ref, id)             ->  POST /api/bookings/:ref/choose
    google.script.run...sendDocuments(ref, files)            ->  POST /api/bookings/:ref/documents
    google.script.run...emailList(...)                       ->  POST /api/share/email
    google.script.run...whatsappList(...)                    ->  POST /api/share/whatsapp
    <?!= rows ?>                                             ->  fetched after login, never inlined

  Every response uses the envelope { status, data, message }.
  A 401 means the session has gone — show the login screen again.
*/
'use strict';

/** Single place the rest of the app talks to the API through. */
async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    credentials: 'same-origin',
    headers: options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' },
    ...options,
  });

  if (response.status === 401) {
    showLogin();
    throw new Error('Please sign in.');
  }

  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload || payload.status !== 'ok') {
    throw new Error((payload && payload.message) || 'Something went wrong. Please try again.');
  }
  return payload.data;
}

function showLogin() {
  // Built with the login screen on feature/login.
}

document.addEventListener('DOMContentLoaded', () => {
  // Boot order, once the UI exists:
  //   1. GET /api/session  -> null means show the login screen
  //   2. signed in         -> load the finder, then GET /api/schedule
  void api;
});
