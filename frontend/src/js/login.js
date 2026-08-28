// If a token already exists — redirect user to the appropriate page
(async function checkExistingToken() {
  // Fail-safe: extract token if it got caught in the redirect param (e.g. from cached dashboard.html)
  const urlParams = new URLSearchParams(window.location.search);
  const redirectParam = urlParams.get('redirect');
  if (redirectParam && redirectParam.includes('token=')) {
    try {
      const redirectSearch = redirectParam.split('?')[1];
      if (redirectSearch) {
        const nestedParams = new URLSearchParams(redirectSearch);
        const nestedToken = nestedParams.get('token');
        if (nestedToken) {
          localStorage.setItem('token', nestedToken);
          // Redirect to the clean page without the token in URL
          window.location.href = redirectParam.split('?')[0];
          return;
        }
      }
    } catch(e) {}
  }

  const t = getToken();
  if (!t) return;
  try {
    const profileRes = await fetch(`${API}/profile/me`, {
      headers: { 'Authorization': `Bearer ${t}` }
    });

    // Token expired or invalid
    if (profileRes.status === 401) {
      localStorage.removeItem('token');
      return;
    }

    // Not active — renew inside the platform (token stays put).
    // NOTE: a 402 here is deliberately left alone so an expired user who
    // opens /login on purpose can still sign into another account.
    if (profileRes.status === 403) {
      window.location.href = '/renewal';
      return;
    }

    if (!profileRes.ok) return;

    const profile = await profileRes.json();
    if (!profile.is_active) {
      window.location.href = '/renewal';
      return;
    }

    window.location.href = profile.onboarding_completed ? 'dashboard.html' : 'onboarding.html';
  } catch(e) {
    // Network error — stay on login page
  }
})();

// Localised string helper — i18n.js exposes window.i18nT (Arabic by default).
function tr(key, fallback) {
  return (typeof window.i18nT === 'function') ? window.i18nT(key, fallback) : (fallback || key);
}

async function login() {
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;

  if (!email || !password) {
    showAlert(tr('errFillAllFields'), 'error');
    return;
  }

  setLoading('loginBtn', true);

  try {
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();

    if (res.ok) {
      saveToken(data.access_token);

      // Save user data in localStorage
      if (data.user) {
        localStorage.setItem('user', JSON.stringify(data.user));
      }

      showAlert(tr('okLoggedIn'), 'success');

      let redirect = 'onboarding.html';
      
      // First: if there's a redirect parameter, use it (as long as it's not login/register)
      const urlParams = new URLSearchParams(window.location.search);
      let redirectParam = urlParams.get('redirect');
      if (redirectParam && !redirectParam.includes('login') && redirectParam.startsWith('/')) {
        redirect = redirectParam.split('?')[0]; // strip extra query string
      } else {
        // Second: determine based on account state
        if (data.user) {
          if (!data.user.is_active) {
            redirect = '/renewal';
          } else if (data.user.onboarding_completed) {
            redirect = 'dashboard.html';
          }
        }
      }

      setTimeout(() => { window.location.href = redirect; }, 1200);
    } else {
      showAlert(data.detail || tr('errWrongCredentials'), 'error');
    }

  } catch {
    showAlert(tr('errNoConnection'), 'error');
  } finally {
    setLoading('loginBtn', false);
  }
}

document.addEventListener('keydown', (e) => { if (e.key === 'Enter') login(); });

// The Google callback bounces failures back here with ?error=. Without this the
// member was returned to a blank login form with no idea what had happened.
// Deferred to DOMContentLoaded because showAlert writes into #alert, which is
// further down the page than this script.
document.addEventListener('DOMContentLoaded', () => {
  const params = new URLSearchParams(window.location.search);
  const reason = params.get('error');
  if (!reason) return;

  const messages = {
    google_failed:    () => tr('errGoogleFailed', "We couldn't finish signing you in with Google. Please try again."),
    email_unverified: () => tr('errGoogleUnverified', 'That Google address is not verified yet. Verify it with Google, then try again.'),
  };
  if (messages[reason]) showAlert(messages[reason](), 'error');

  // Drop only `error`, so a refresh doesn't replay the message. ?redirect= has
  // to survive — login() reads it to decide where to send the member next.
  params.delete('error');
  const query = params.toString();
  history.replaceState(null, '', window.location.pathname + (query ? '?' + query : ''));
});
