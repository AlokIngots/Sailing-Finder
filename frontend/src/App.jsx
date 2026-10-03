import { useCallback, useEffect, useState } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';

import api from './api.js';
import Bookings from './components/Bookings.jsx';
import Finder from './components/Finder.jsx';
import Login from './components/Login.jsx';
import Shipment from './components/Shipment.jsx';
import Users from './components/Users.jsx';

/**
 * Routes plus the auth gate.
 *
 * On load this calls GET /api/me and nothing else. Until that answers with a
 * user, no other request is made — the schedule is never fetched, let alone
 * shown, before a successful sign-in.
 *
 * The gate here is for the person using the app. The real one is require_auth
 * on the server: hiding a view in the browser is not a security boundary.
 */
export default function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);
  const [bootError, setBootError] = useState('');

  useEffect(() => {
    const controller = new AbortController();

    api
      .me(controller.signal)
      .then(setUser)
      .catch((err) => {
        if (err.name === 'AbortError') return;
        // 401 is the ordinary "not signed in yet" answer, not a failure worth
        // showing. Anything else means the server is unreachable or broken,
        // and saying so beats a login box that silently never works.
        if (!err.isUnauthorised) setBootError(err.message);
        setUser(null);
      })
      .finally(() => setChecking(false));

    return () => controller.abort();
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // Already gone server-side, or the network dropped. Either way this
      // browser is done with the session.
    } finally {
      setUser(null);
    }
  }, []);

  if (checking) {
    return (
      <p className="boot" role="status">
        Loading…
      </p>
    );
  }

  if (!user) {
    return <Login onSignedIn={setUser} serverError={bootError} />;
  }

  const isAdmin = user.role === 'admin';

  return (
    <div className="app">
      <header className="app-header">
        <span className="app-title">Sailing Finder</span>
        {/* Only admins have more than one screen to move between. */}
        {isAdmin ? (
          <nav className="app-nav" aria-label="Main">
            <NavLink to="/" end>
              Finder
            </NavLink>
            <NavLink to="/users">Users</NavLink>
          </nav>
        ) : null}
        <span className="app-user" title={user.role}>
          {user.name}
        </span>
        <button type="button" className="link" onClick={signOut}>
          Sign out
        </button>
      </header>

      <Routes>
        <Route path="/" element={<Finder user={user} />} />
        <Route path="/bookings" element={<Bookings user={user} />} />
        <Route path="/bookings/:ref" element={<Shipment user={user} />} />
        {/* A non-admin typing /users falls through to the redirect below; the
            API behind the screen answers them 403 regardless. */}
        {isAdmin ? <Route path="/users" element={<Users />} /> : null}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
