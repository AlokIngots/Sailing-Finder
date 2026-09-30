import { useEffect, useRef, useState } from 'react';

import api from '../api.js';

/**
 * Sign-in screen.
 *
 * New work — the reference UI has no login, so there is nothing to match it
 * against. Styled from the brand colours only: navy #000C2E on white, light
 * theme, no dark mode.
 *
 * The form never says which half was wrong. The server returns one message for
 * an unknown username and a wrong password alike, and this just shows it.
 */
export default function Login({ onSignedIn, serverError = '' }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(serverError);
  const [busy, setBusy] = useState(false);
  const errorRef = useRef(null);

  useEffect(() => {
    setError(serverError);
  }, [serverError]);

  // Move focus to the error so a screen reader announces it, and so the
  // failure is impossible to miss on a phone where it may be below the fold.
  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  async function submit(event) {
    event.preventDefault();
    if (busy) return;

    setError('');
    setBusy(true);
    try {
      const user = await api.login(username.trim(), password);
      setPassword('');
      onSignedIn(user);
    } catch (err) {
      setError(err.message);
      setPassword('');
    } finally {
      setBusy(false);
    }
  }

  const canSubmit = username.trim() !== '' && password !== '' && !busy;

  return (
    <main className="login">
      <form className="login-card" onSubmit={submit} noValidate>
        <h1 className="login-title">Sailing Finder</h1>
        <p className="login-sub">Alok Ingots (Mumbai) Pvt. Ltd.</p>

        <div className="field">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck="false"
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={busy}
          />
        </div>

        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={busy}
          />
        </div>

        {/* Always visible, never a silent failure. */}
        {error ? (
          <p className="error" role="alert" tabIndex={-1} ref={errorRef}>
            {error}
          </p>
        ) : null}

        <button type="submit" className="primary" disabled={!canSubmit}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>

        <p className="login-foot">
          No sign-up — accounts are created by an administrator.
        </p>
      </form>
    </main>
  );
}
