import { useCallback, useEffect, useState } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';

import api from './api.js';
import Bookings from './components/Bookings.jsx';
import Finder from './components/Finder.jsx';
import Login from './components/Login.jsx';
import Shipment from './components/Shipment.jsx';

/**
 * The app shell — a port of the reference's sticky `header.top` — plus routes
 * and the auth gate.
 *
 * On load this calls GET /api/me and nothing else. Until that answers with a
 * user, no other request is made: the schedule is never fetched, let alone
 * shown, before a successful sign-in.
 *
 * The gate here is for the person using the app. The real one is require_auth on
 * the server; hiding a view in the browser is not a security boundary.
 */
export default function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);
  const [bootError, setBootError] = useState('');
  const [customerView, setCustomerView] = useState(false);

  const navigate = useNavigate();
  const { pathname } = useLocation();

  useEffect(() => {
    const controller = new AbortController();

    api
      .me(controller.signal)
      .then(setUser)
      .catch((err) => {
        if (err.name === 'AbortError') return;
        // 401 is the ordinary "not signed in yet" answer, not a failure worth
        // showing. Anything else means the server is unreachable or broken, and
        // saying so beats a login box that silently never works.
        if (!err.isUnauthorised) setBootError(err.message);
        setUser(null);
      })
      .finally(() => setChecking(false));

    return () => controller.abort();
  }, []);

  /**
   * Customer view is a class on <body>, exactly as the reference does it:
   * `body.customer .internal{display:none!important}`. Keeping it there means
   * no component needs to know the toggle exists.
   */
  useEffect(() => {
    document.body.classList.toggle('customer', customerView);
    return () => document.body.classList.remove('customer');
  }, [customerView]);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // Already gone server-side, or the network dropped. Either way this
      // browser is done with the session.
    } finally {
      setUser(null);
      setCustomerView(false);
    }
  }, []);

  if (checking) return null; // the gate covers the screen anyway; no flash of layout

  if (!user) return <Login onSignedIn={setUser} serverError={bootError} />;

  const view = pathname.startsWith('/bookings') ? 'bookings' : 'finder';

  return (
    <>
      <header className="top">
        <div className="top-in">
          <div className="mark">
            <span />
          </div>
          <div className="brand">
            <h1>Sailing Finder</h1>
            <p>Nhava Sheva &rarr; Europe &amp; Mediterranean</p>
          </div>

          <nav className="nav">
            <button
              type="button"
              aria-current={view === 'finder'}
              onClick={() => navigate('/')}
            >
              Find sailings
            </button>
            <button
              type="button"
              aria-current={view === 'bookings'}
              onClick={() => navigate('/bookings')}
            >
              My bookings{' '}
              {/* Count arrives with feature/bookings, which owns that list. */}
              <span className="badge" id="navCount">
                0
              </span>
            </button>
          </nav>

          <label
            className="viewtoggle internal"
            title="Hide the internal tools for a clean screen to show a customer"
          >
            <input
              type="checkbox"
              id="custView"
              checked={customerView}
              onChange={(e) => setCustomerView(e.target.checked)}
            />
            <span className="switch" />
            Customer view
          </label>

          <button
            type="button"
            className="btn ghost logoutbtn"
            id="logoutBtn"
            title="Sign out"
            onClick={signOut}
          >
            Sign out
          </button>
        </div>
      </header>

      <Routes>
        <Route path="/" element={<Finder user={user} />} />
        <Route path="/bookings" element={<Bookings user={user} />} />
        <Route path="/bookings/:ref" element={<Shipment user={user} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {/* The reference's bottom-centre toast. lib/flash.js drives it. */}
      <div id="flash" />
    </>
  );
}
