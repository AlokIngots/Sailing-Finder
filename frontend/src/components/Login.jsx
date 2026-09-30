import { useState } from 'react';

import api from '../api.js';

/**
 * Sign-in screen. New — the reference UI has no login, so there is nothing to
 * match it against yet. The markup is deliberately plain; it takes the app's
 * navy/white styling once reference/Index.html is supplied.
 *
 * The form never says which half was wrong. The server returns one message for
 * a bad username and a bad password alike, and this just shows it.
 */
export default function Login({ onSignedIn }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const user = await api.login(username.trim(), password);
      onSignedIn(user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login">
      <form className="login-card" onSubmit={submit}>
        <h1 className="login-title">Sailing Finder</h1>
        <p className="login-sub">Alok Ingots (Mumbai) Pvt. Ltd.</p>

        <label htmlFor="username">Username</label>
        <input
          id="username"
          name="username"
          autoComplete="username"
          autoFocus
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />

        <label htmlFor="password">Password</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {/* Errors are always visible — never a silent failure. */}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" disabled={busy || !username || !password}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  );
}
