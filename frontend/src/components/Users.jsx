import { useCallback, useEffect, useRef, useState } from 'react';

import api from '../api.js';

const EMPTY_FORM = { username: '', name: '', role: 'user', password: '' };
const MIN_PASSWORD = 8;

const ROLE_LABEL = { admin: 'Admin', user: 'User' };

/**
 * Users — admin only. Add an account, see who has one, remove one.
 *
 * App.jsx only routes admins here, but that is for convenience: every call
 * below is checked by require_admin on the server, which answers 403 to anyone
 * else.
 *
 * Removing is a two-step tap (Remove, then Confirm) rather than a browser
 * confirm() box, so it works the same on a phone.
 */
export default function Users() {
  const [rows, setRows] = useState(null);
  const [loadError, setLoadError] = useState('');

  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);

  const [notice, setNotice] = useState('');
  const [confirming, setConfirming] = useState('');
  const [removing, setRemoving] = useState('');
  const [listError, setListError] = useState('');

  const formErrorRef = useRef(null);

  const load = useCallback((signal) => {
    setLoadError('');
    return api
      .users(signal)
      .then(setRows)
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setLoadError(err.message);
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    if (formError) formErrorRef.current?.focus();
  }, [formError]);

  function setField(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function addUser(event) {
    event.preventDefault();
    if (saving) return;

    setFormError('');
    setNotice('');
    setSaving(true);
    try {
      const created = await api.createUser({
        username: form.username.trim(),
        name: form.name.trim(),
        role: form.role,
        password: form.password,
      });
      setForm(EMPTY_FORM);
      setNotice(`Added ${created.name} (${created.username}).`);
      await load();
    } catch (err) {
      setFormError(err.message);
      setField('password', '');
    } finally {
      setSaving(false);
    }
  }

  async function removeUser(username) {
    setListError('');
    setNotice('');
    setRemoving(username);
    try {
      await api.removeUser(username);
      setNotice(`Removed ${username}. They have been signed out.`);
      setConfirming('');
      await load();
    } catch (err) {
      setListError(err.message);
    } finally {
      setRemoving('');
    }
  }

  const canSubmit =
    form.username.trim().length >= 2 &&
    form.name.trim() !== '' &&
    form.password.length >= MIN_PASSWORD &&
    !saving;

  return (
    <section className="users">
      <h1 className="page-title">Users</h1>

      <form className="panel user-form" onSubmit={addUser} noValidate>
        <h2 className="panel-title">Add a user</h2>

        <div className="user-form-grid">
          <div className="field">
            <label htmlFor="nu-username">Username</label>
            <input
              id="nu-username"
              autoComplete="off"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck="false"
              value={form.username}
              onChange={(e) => setField('username', e.target.value)}
              disabled={saving}
            />
          </div>

          <div className="field">
            <label htmlFor="nu-name">Full name</label>
            <input
              id="nu-name"
              autoComplete="off"
              value={form.name}
              onChange={(e) => setField('name', e.target.value)}
              disabled={saving}
            />
          </div>

          <div className="field">
            <label htmlFor="nu-role">Role</label>
            <select
              id="nu-role"
              value={form.role}
              onChange={(e) => setField('role', e.target.value)}
              disabled={saving}
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>

          <div className="field">
            <label htmlFor="nu-password">Password</label>
            <input
              id="nu-password"
              type="password"
              autoComplete="new-password"
              value={form.password}
              onChange={(e) => setField('password', e.target.value)}
              disabled={saving}
              aria-describedby="nu-password-hint"
            />
            <span id="nu-password-hint" className="hint">
              At least {MIN_PASSWORD} characters.
            </span>
          </div>
        </div>

        {formError ? (
          <p className="error" role="alert" tabIndex={-1} ref={formErrorRef}>
            {formError}
          </p>
        ) : null}

        <div className="user-form-actions">
          <button type="submit" className="primary" disabled={!canSubmit}>
            {saving ? 'Adding…' : 'Add user'}
          </button>
        </div>
      </form>

      {notice ? (
        <p className="notice" role="status">
          {notice}
        </p>
      ) : null}

      <div className="panel">
        <h2 className="panel-title">
          Existing users{rows ? <span className="count"> · {rows.length}</span> : null}
        </h2>

        {listError ? (
          <p className="error" role="alert">
            {listError}
          </p>
        ) : null}

        {loadError ? (
          <div className="load-failed">
            <p className="error" role="alert">
              Could not load users: {loadError}
            </p>
            <button type="button" onClick={() => load()}>
              Try again
            </button>
          </div>
        ) : rows === null ? (
          <p className="result-count" role="status">
            Loading…
          </p>
        ) : rows.length === 0 ? (
          <p className="empty">No users yet.</p>
        ) : (
          <ul className="user-list">
            {rows.map((row) => (
              <li key={row.username} className="user-row">
                <div className="user-who">
                  <span className="user-name">{row.name}</span>
                  <span className="user-username">{row.username}</span>
                </div>

                <div className="user-tags">
                  <span className={row.role === 'admin' ? 'tag tag-direct' : 'tag'}>
                    {ROLE_LABEL[row.role] || row.role}
                  </span>
                  {row.is_self ? <span className="tag">You</span> : null}
                </div>

                <div className="user-actions">
                  {row.is_self ? null : confirming === row.username ? (
                    <>
                      <button
                        type="button"
                        className="danger"
                        onClick={() => removeUser(row.username)}
                        disabled={removing === row.username}
                      >
                        {removing === row.username ? 'Removing…' : 'Confirm remove'}
                      </button>
                      <button
                        type="button"
                        className="link"
                        onClick={() => setConfirming('')}
                        disabled={removing === row.username}
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        setListError('');
                        setConfirming(row.username);
                      }}
                      disabled={Boolean(removing)}
                      aria-label={`Remove ${row.name}`}
                    >
                      Remove
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
