(function () {
  AuthClient.requireAuth();

  const user = AuthClient.getUser();
  document.getElementById('user-name').textContent = user ? user.full_name : '';
  document.getElementById('logout-btn').addEventListener('click', async () => {
    await AuthClient.logout();
    window.location.replace('login.html');
  });

  // ----- Relógio -----
  const clockEl = document.getElementById('clock');
  function tickClock() {
    clockEl.textContent = new Date().toLocaleString('pt-BR');
  }
  tickClock();
  setInterval(tickClock, 1000);

  // ----- Estado das cotações em memória -----
  // instrumento_id -> último dado recebido
  const quotesById = new Map();
  // praca_codigo -> ordem de exibição fixa (café)
  const PRACA_ORDEM = { NY: 0, BMF: 1, LONDRES: 2 };

  function formatNumber(value, decimals) {
    if (value === null || value === undefined) return '—';
    return value.toLocaleString('pt-BR', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  }

  function applyQuote(quote, { flash = true } = {}) {
    const previous = quotesById.get(quote.instrumento_id);
    quotesById.set(quote.instrumento_id, quote);
    renderAll();
    if (flash && previous && previous.preco_ultimo !== quote.preco_ultimo) {
      flashRow(quote.instrumento_id, quote.preco_ultimo, previous.preco_ultimo);
    }
  }

  function flashRow(instrumentoId, novo, antigo) {
    const row = document.querySelector(`[data-instrumento-id="${instrumentoId}"]`);
    if (!row) return;
    row.classList.remove('flash-up', 'flash-down');
    if (novo != null && antigo != null) {
      row.classList.add(novo > antigo ? 'flash-up' : novo < antigo ? 'flash-down' : '');
    }
    window.setTimeout(() => row.classList.remove('flash-up', 'flash-down'), 1200);
  }

  function renderAll() {
    renderDolar();
    renderCafe();
  }

  function renderDolar() {
    const section = document.getElementById('dolar-section');
    const container = document.getElementById('dolar-cards');
    const items = [...quotesById.values()].filter((q) => q.ativo === 'Dólar');
    section.hidden = items.length === 0;
    container.innerHTML = '';
    for (const q of items) {
      const card = document.createElement('div');
      card.className = 'dolar-card';
      card.dataset.instrumentoId = q.instrumento_id;
      const variClass = varClass(q.variacao_pct);
      card.innerHTML = `
        <div class="dolar-card-label">${q.vencimento_label}</div>
        <div class="dolar-card-price">R$ ${formatNumber(q.preco_ultimo, 4)}</div>
        <div class="dolar-card-var ${variClass}">${formatVariacao(q.variacao_pct)}</div>
      `;
      container.appendChild(card);
    }
  }

  function renderCafe() {
    const container = document.getElementById('pracas-container');
    const cafeItems = [...quotesById.values()].filter((q) => q.ativo === 'Café');

    const byPraca = new Map();
    for (const q of cafeItems) {
      if (!byPraca.has(q.praca)) byPraca.set(q.praca, []);
      byPraca.get(q.praca).push(q);
    }

    const pracasOrdenadas = [...byPraca.keys()].sort(
      (a, b) => (PRACA_ORDEM[praCodigo(a, cafeItems)] ?? 99) - (PRACA_ORDEM[praCodigo(b, cafeItems)] ?? 99)
    );

    container.innerHTML = '';
    for (const praca of pracasOrdenadas) {
      const items = byPraca.get(praca).sort((a, b) => a.vencimento_label.localeCompare(b.vencimento_label));
      const table = document.createElement('table');
      table.className = 'quotes-table';
      table.innerHTML = `
        <caption>${praca}</caption>
        <thead>
          <tr>
            <th>Vencimento</th>
            <th>Ticker</th>
            <th>Abertura</th>
            <th>Mínima</th>
            <th>Máxima</th>
            <th>Ajuste ant.</th>
            <th>Último</th>
            <th>Var. %</th>
          </tr>
        </thead>
        <tbody></tbody>
      `;
      const tbody = table.querySelector('tbody');
      for (const q of items) {
        const tr = document.createElement('tr');
        tr.dataset.instrumentoId = q.instrumento_id;
        tr.innerHTML = `
          <td>${q.vencimento_label}</td>
          <td class="ticker">${q.ticker}</td>
          <td>${formatNumber(q.preco_abertura, 2)}</td>
          <td>${formatNumber(q.preco_minimo, 2)}</td>
          <td>${formatNumber(q.preco_maximo, 2)}</td>
          <td>${formatNumber(q.preco_ajuste_anterior, 2)}</td>
          <td class="preco-ultimo">${formatNumber(q.preco_ultimo, 2)}</td>
          <td class="${varClass(q.variacao_pct)}">${formatVariacao(q.variacao_pct)}</td>
        `;
        tbody.appendChild(tr);
      }
      container.appendChild(table);
    }
  }

  function praCodigo(nome, items) {
    const found = items.find((i) => i.praca === nome);
    return found ? found.praca_codigo : null;
  }

  function varClass(pct) {
    if (pct === null || pct === undefined) return '';
    return pct > 0 ? 'positivo' : pct < 0 ? 'negativo' : '';
  }

  function formatVariacao(pct) {
    if (pct === null || pct === undefined) return '—';
    const sign = pct > 0 ? '+' : '';
    return `${sign}${formatNumber(pct, 2)}%`;
  }

  // ----- WebSocket em tempo real -----
  const statusEl = document.getElementById('connection-status');
  let ws = null;
  let reconnectDelay = 1000;
  let pingInterval = null;

  function setStatus(state) {
    statusEl.classList.remove('status-connecting', 'status-online', 'status-offline');
    if (state === 'online') {
      statusEl.classList.add('status-online');
      statusEl.textContent = 'ao vivo';
    } else if (state === 'offline') {
      statusEl.classList.add('status-offline');
      statusEl.textContent = 'reconectando...';
    } else {
      statusEl.classList.add('status-connecting');
      statusEl.textContent = 'conectando...';
    }
  }

  function connectWebSocket() {
    const token = AuthClient.getToken();
    if (!token) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/quotes`);

    ws.addEventListener('open', () => {
      ws.send(JSON.stringify({ token }));
      reconnectDelay = 1000;
      pingInterval = window.setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }));
      }, 20000);
    });

    ws.addEventListener('message', (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'snapshot') {
        setStatus('online');
        for (const q of data.instrumentos) applyQuote(q, { flash: false });
      } else if (data.type === 'quotes_update') {
        setStatus('online');
        for (const q of data.instrumentos) applyQuote(q);
      }
    });

    ws.addEventListener('close', (event) => {
      window.clearInterval(pingInterval);
      setStatus('offline');
      if (event.code === 4001 || event.code === 4003) {
        // Sessão encerrada (logout em outra tela ou token inválido).
        AuthClient.clearSession();
        window.location.replace('login.html');
        return;
      }
      scheduleReconnect();
    });

    ws.addEventListener('error', () => {
      ws.close();
    });
  }

  function scheduleReconnect() {
    setStatus('connecting');
    window.setTimeout(connectWebSocket, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 30000);
  }

  connectWebSocket();
})();
