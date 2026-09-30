import { useEffect, useState } from 'react';

import api from '../api.js';

/**
 * The sign-in gate — a port of the reference's `#gate`.
 *
 * Wrapped in a <form> so Enter submits, which the reference's click-only button
 * does not do. That is the one addition; the markup, classes and copy are the
 * reference's.
 *
 * The form never says which half was wrong. The server returns one message for
 * an unknown username and a wrong password alike, and this just shows it.
 */
export default function Login({ onSignedIn, serverError = '' }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(serverError);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setError(serverError);
  }, [serverError]);

  async function submit(event) {
    event.preventDefault();
    if (busy) return;

    setError('');
    setBusy(true);
    try {
      const signedIn = await api.login(username.trim(), password);
      setPassword('');
      onSignedIn(signedIn);
    } catch (err) {
      setError(err.message);
      setPassword('');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div id="gate">
      <form className="box" onSubmit={submit} noValidate>
        <div className="brandrow">
          <div className="mark">
            <span />
          </div>
          <div>
            <h2>Sailing Finder</h2>
            <p>Alok Ingots &middot; sign in to continue</p>
          </div>
        </div>

        <label htmlFor="lgUser">Username</label>
        <input
          type="text"
          id="lgUser"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck="false"
          autoFocus
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={busy}
        />

        <label htmlFor="lgPass">Password</label>
        <input
          type="password"
          id="lgPass"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={busy}
        />

        {/* Always rendered, so the box does not jump when a message appears. */}
        <div className="err" id="lgErr" role="alert">
          {error}
        </div>

        <button
          type="submit"
          className="btn primary"
          id="lgBtn"
          disabled={busy || !username.trim() || !password}
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}
