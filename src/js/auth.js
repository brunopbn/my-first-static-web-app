// Cliente de autenticação. Guarda o token em sessionStorage (por aba), o que
// combina naturalmente com a regra de "telas simultâneas": cada aba/janela
// nova precisa logar de novo e disputa o mesmo limite de sessões do usuário.
const AuthClient = (() => {
  const TOKEN_KEY = 'painel_token';
  const USER_KEY = 'painel_user';

  function getToken() {
    return sessionStorage.getItem(TOKEN_KEY);
  }

  function getUser() {
    const raw = sessionStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  }

  function _setSession(token, user) {
    sessionStorage.setItem(TOKEN_KEY, token);
    sessionStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  function clearSession() {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
  }

  async function login(email, password) {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      if (response.status === 409) {
        throw new Error(data.detail || 'Limite de telas simultâneas atingido.');
      }
      throw new Error(data.detail || 'E-mail ou senha inválidos.');
    }

    const data = await response.json();
    _setSession(data.access_token, data.user);
    return data;
  }

  async function logout() {
    const token = getToken();
    clearSession();
    if (!token) return;
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (err) {
      // Falha ao avisar o servidor não deve travar o logout local.
    }
  }

  async function authFetch(path, options = {}) {
    const token = getToken();
    const headers = new Headers(options.headers || {});
    if (token) headers.set('Authorization', `Bearer ${token}`);

    const response = await fetch(path, { ...options, headers });
    if (response.status === 401) {
      clearSession();
      window.location.replace('login.html');
      throw new Error('Sessão expirada.');
    }
    return response;
  }

  function requireAuth() {
    if (!getToken()) {
      window.location.replace('login.html');
    }
  }

  return { getToken, getUser, login, logout, authFetch, requireAuth, clearSession };
})();
