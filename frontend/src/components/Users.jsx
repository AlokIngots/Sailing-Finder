import { useCallback, useEffect, useState } from 'react';

import api from '../api.js';

const EMPTY_FORM = { username: '', name: '', role: 'user', password: '' };
const MIN_PASSWORD = 8;

const ROLE_LABEL = { admin: 'Admin', user: 'User' };

/**
 * Users — admin only. Add an account, see who has one, remove one.
 *
 * Not in reference/Index.html; built from its patterns (.bkhead, .panel,
 * .control/.lbl, .btn, and rows shaped like .brow) so it sits in the same
 * shell without changing it.
 *
 * App.jsx only routes admins here, but that is for convenience: every call
 * below is checked by require_admin on the server, which answers 403 to anyone
 * else.
 *
 * Removing is a two-step tap (Remove, then Confirm remove) rather than a
 * browser confirm() box, so it works the same on a phone.
 */
export default function Users({ flash }) {
  const [rows, setRows] = useState(null);
  const [loadError, setLoadError] = useState('');

  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);

  const [confirming, setConfirming] = useState('');
  const [removing, setRemoving] = useState('');

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

  function setField(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function addUser(event) {
    event.preventDefault();
    if (saving) return;

    setFormError('');
    setSaving(true);
    try {
      const created = await api.createUser({
        username: form.username.trim(),
        name: form.name.trim(),
        role: form.role,
        password: form.password,
      });
      setForm(EMPTY_FORM);
      flash(`Added ${created.name} (${created.username}).`);
      await load();
    } catch (err) {
      setFormError(err.message);
      setField('password', '');
    } finally {
      setSaving(false);
    }
  }

  async function removeUser(username) {
    setRemoving(username);
    try {
      await api.removeUser(username);
      flash(`Removed ${username}. They have been signed out.`);
      setConfirming('');
      await load();
    } catch (err) {
      flash(`Could not remove: ${err.message}`);
    } finally {
      setRemoving('');
    }
  }

  const canSubmit =
    form.username.trim().length >= 2 &&
    form.name.trim() !== '' &&
    form.password.length >= MIN_PASSWORD &&
    !saving;

  let list = null;
  if (loadError) {
    list = (
      <div className="empty failed" role="alert" style={{ marginTop: 10 }}>
        <h3>Couldn&apos;t load users</h3>
        <div>{loadError}</div>
        <button type="button" className="btn" onClick={() => load()}>
          Try again
        </button>
      </div>
    );
  } else if (rows && !rows.length) {
    list = (
      <div className="empty" style={{ marginTop: 10 }}>
        <h3>No users yet</h3>
        <div>Add the first one above.</div>
      </div>
    );
  } else if (rows) {
    list = rows.map((row) => (
      <div key={row.username} className="urow">
        <div className="bl">
          <div className="ves">{row.name}</div>
          <div className="rt">{row.username}</div>
        </div>
        <div className="tags">
          <span className={row.role === 'admin' ? 'chip quotes' : 'chip plain'}>
            {ROLE_LABEL[row.role] || row.role}
          </span>
          {row.is_self ? <span className="chip booked">You</span> : null}
        </div>
        <div className="uact">
          {row.is_self ? null : confirming === row.username ? (
            <>
              <button
                type="button"
                className="btn sm danger"
                onClick={() => removeUser(row.username)}
                disabled={removing === row.username}
              >
                {removing === row.username ? 'Removing…' : 'Confirm remove'}
              </button>
              <button
                type="button"
                className="btn ghost sm"
                onClick={() => setConfirming('')}
                disabled={removing === row.username}
              >
                Cancel
              </button>
            </>
          ) : (
            <button
              type="button"
              className="btn sm"
              onClick={() => setConfirming(row.username)}
              disabled={Boolean(removing)}
              aria-label={`Remove ${row.name}`}
            >
              Remove
            </button>
          )}
        </div>
      </div>
    ));
  }

  return (
    <div className="view active users" id="v-users">
      <div className="wrap">
        <div className="bkhead">
          <h2>Users</h2>
          <p>Who can sign in, and as what.</p>
        </div>

        <form className="panel" onSubmit={addUser} noValidate>
          <h4>Add a user</h4>
          <div className="row">
            <div className="control">
              <label className="lbl" htmlFor="nuUser">Username</label>
              <input
                type="text"
                id="nuUser"
                autoComplete="off"
                autoCapitalize="none"
                spellCheck="false"
                value={form.username}
                onChange={(e) => setField('username', e.target.value)}
                disabled={saving}
              />
            </div>
            <div className="control">
              <label className="lbl" htmlFor="nuName">Full name</label>
              <input
                type="text"
                id="nuName"
                autoComplete="off"
                value={form.name}
                onChange={(e) => setField('name', e.target.value)}
                disabled={saving}
              />
            </div>
          </div>
          <div className="row">
            <div className="control">
              <label className="lbl" htmlFor="nuRole">Role</label>
              <select id="nuRole" value={form.role} onChange={(e) => setField('role', e.target.value)} disabled={saving}>
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div className="control">
              <label className="lbl" htmlFor="nuPass">Password</label>
              <input
                type="password"
                id="nuPass"
                autoComplete="new-password"
                value={form.password}
                onChange={(e) => setField('password', e.target.value)}
                disabled={saving}
                aria-describedby="nuPassHint"
              />
              <div className="hint" id="nuPassHint">
                At least {MIN_PASSWORD} characters.
              </div>
            </div>
          </div>
          <div className="err" role="alert">
            {formError}
          </div>
          <div className="actions" style={{ marginTop: 4 }}>
            <button type="submit" className="btn primary" disabled={!canSubmit}>
              {saving ? 'Adding…' : 'Add user'}
            </button>
          </div>
        </form>

        <div className="bkhead">
          <h2 style={{ fontSize: 16 }}>Existing users</h2>
          {rows ? <p>{rows.length}</p> : null}
        </div>
        <div>{list}</div>
        <div className="foot">Removing someone signs them out at once. Their bookings stay.</div>
      </div>
    </div>
  );
}
