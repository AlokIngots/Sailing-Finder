import { useCallback, useEffect, useRef, useState } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';

import api from './api.js';
import { clearApiCache } from './pwa.js';
import Bookings from './components/Bookings.jsx';
import Finder from './components/Finder.jsx';
import Login from './components/Login.jsx';
import Rates from './components/Rates.jsx';
import Shipment from './components/Shipment.jsx';
import Users from './components/Users.jsx';

/**
 * Routes, the auth gate, and the app shell from reference/Index.html: the
 * sticky header with the logo mark, the Find sailings / My bookings tabs, the
 * Customer view switch, and the #flash toast.
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

  const [customerView, setCustomerView] = useState(false);
  const [bookingCount, setBookingCount] = useState(0);
  const [flashText, setFlashText] = useState('');
  const [flashOn, setFlashOn] = useState(false);
  const flashTimer = useRef(null);

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
        // showing. Anything else means the server is unreachable or broken,
        // and saying so beats a login box that silently never works.
        if (!err.isUnauthorised) setBootError(err.message);
        setUser(null);
      })
      .finally(() => setChecking(false));

    return () => controller.abort();
  }, []);

  // The reference hides every `.internal` element with `body.customer`, so the
  // switch drives that class rather than threading a prop through each view.
  useEffect(() => {
    document.body.classList.toggle('customer', Boolean(user) && customerView);
    return () => document.body.classList.remove('customer');
  }, [user, customerView]);

  // The badge on My bookings. Until the bookings API is built it answers an
  // error, and the badge stays at 0 exactly as the reference shows it.
  useEffect(() => {
    if (!user) return undefined;
    const controller = new AbortController();
    api
      .bookings(controller.signal)
      .then((list) => setBookingCount(Array.isArray(list) ? list.length : 0))
      .catch(() => setBookingCount(0));
    return () => controller.abort();
  }, [user]);

  useEffect(() => () => clearTimeout(flashTimer.current), []);

  const flash = useCallback((message) => {
    setFlashText(message);
    setFlashOn(true);
    clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setFlashOn(false), 4500);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // Already gone server-side, or the network dropped. Either way this
      // browser is done with the session.
    } finally {
      // The offline copies of this user's data go with the session.
      clearApiCache();
      setCustomerView(false);
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
  const onBookings = pathname.startsWith('/bookings');
  const onUsers = pathname === '/users';
  const onRates = pathname === '/rates';
  const onFinder = !onBookings && !onUsers && !onRates;

  function go(path) {
    navigate(path);
    window.scrollTo(0, 0);
  }

  return (
    <>
      <header className="top">
        <div className="top-in">
          <div className="mark">
            <span />
          </div>
          <div className="brand">
            <h1>Sailing Finder</h1>
            <p>Nhava Sheva → Europe &amp; Mediterranean</p>
          </div>
          <nav className="nav">
            <button type="button" aria-current={onFinder ? 'true' : 'false'} onClick={() => go('/')}>
              Find sailings
            </button>
            <button type="button" aria-current={onBookings ? 'true' : 'false'} onClick={() => go('/bookings')}>
              My bookings <span className="badge">{bookingCount}</span>
            </button>
            {/* Internal (rates are not for a customer's eyes), so Customer view hides it. */}
            <button
              type="button"
              className="internal"
              aria-current={onRates ? 'true' : 'false'}
              onClick={() => go('/rates')}
            >
              Rate summary
            </button>
            {/* Admin only, and an internal tool, so Customer view hides it. */}
            {isAdmin ? (
              <button
                type="button"
                className="internal"
                aria-current={onUsers ? 'true' : 'false'}
                onClick={() => go('/users')}
              >
                Users
              </button>
            ) : null}
          </nav>
          {/* Not .internal (the reference marks it so): hidden by its own
              switch, Customer view would have no way back out. */}
          <label className="viewtoggle" title="Hide the internal tools for a clean screen to show a customer">
            <input
              type="checkbox"
              checked={customerView}
              onChange={(e) => setCustomerView(e.target.checked)}
            />
            <span className="switch" />
            Customer view
          </label>
          <button type="button" className="btn ghost logoutbtn" title="Sign out" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>

      <Routes>
        <Route path="/" element={<Finder flash={flash} />} />
        <Route path="/bookings" element={<Bookings />} />
        <Route path="/bookings/:ref" element={<Shipment />} />
        <Route path="/rates" element={<Rates flash={flash} isAdmin={isAdmin} />} />
        {/* A non-admin typing /users falls through to the redirect below; the
            API behind the screen answers them 403 regardless. */}
        {isAdmin ? <Route path="/users" element={<Users flash={flash} />} /> : null}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      <div id="flash" className={flashOn ? 'show' : ''} role="status" aria-live="polite">
        {flashText}
      </div>
    </>
  );
}
