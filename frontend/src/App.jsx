import { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import api from './api.js';
import Bookings from './components/Bookings.jsx';
import Finder from './components/Finder.jsx';
import Login from './components/Login.jsx';
import Shipment from './components/Shipment.jsx';

/**
 * Routes plus the auth gate.
 *
 * Nothing renders until /api/session has answered, so the schedule is never
 * requested — let alone shown — before a successful login. The gate here is a
 * convenience for the user; the real one is require_auth on every /api call.
 *
 * SCAFFOLD: the three views are placeholders until reference/Index.html is
 * supplied. The session handling below is real.
 */
export default function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let alive = true;
    api
      .session()
      .then((data) => alive && setUser(data))
      .catch(() => alive && setUser(null))
      .finally(() => alive && setChecking(false));
    return () => {
      alive = false;
    };
  }, []);

  async function signOut() {
    try {
      await api.logout();
    } finally {
      setUser(null);
    }
  }

  if (checking) {
    return <p className="boot">Loading…</p>;
  }

  if (!user) {
    return <Login onSignedIn={setUser} />;
  }

  return (
    <div className="app">
      <header className="app-header">
        <span className="app-title">Sailing Finder</span>
        <span className="app-user">{user.name}</span>
        <button type="button" className="link" onClick={signOut}>
          Sign out
        </button>
      </header>

      <Routes>
        <Route path="/" element={<Finder user={user} />} />
        <Route path="/bookings" element={<Bookings user={user} />} />
        <Route path="/bookings/:ref" element={<Shipment user={user} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
