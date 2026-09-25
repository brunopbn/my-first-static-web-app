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
  // praca_codigo -> ordem de exibição fixa (café primeiro, dólar por último)
  const PRACA_ORDEM = { NY: 0, BMF: 1, LONDRES: 2, BALCAO: 99 };

  function formatNumber(value, decimals) {
    if (value === null || value === undefined) return '';
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
    if (novo != null && antigo != null && novo !== antigo) {
      row.classList.add(novo > antigo ? 'flash-up' : 'flash-down');
    }
    window.setTimeout(() => row.classList.remove('flash-up', 'flash-down'), 1200);
  }

  function varClass(pct) {
    if (pct === null || pct === undefined) return '';
    return pct > 0 ? 'positivo' : pct < 0 ? 'negativo' : '';
  }

  function bandLabel(codigo, nome) {
    return codigo === 'BALCAO' ? 'DÓLAR' : nome.toUpperCase();
  }

  function renderAll() {
    const tbody = document.getElementById('quotes-body');
    const items = [...quotesById.values()];

    const byPraca = new Map();
    for (const q of items) {
      if (!byPraca.has(q.praca)) byPraca.set(q.praca, { codigo: q.praca_codigo, items: [] });
      byPraca.get(q.praca).items.push(q);
    }

    const pracasOrdenadas = [...byPraca.entries()].sort(
      (a, b) => (PRACA_ORDEM[a[1].codigo] ?? 50) - (PRACA_ORDEM[b[1].codigo] ?? 50)
    );

    tbody.innerHTML = '';
    for (const [pracaNome, { codigo, items: pracaItems }] of pracasOrdenadas) {
      const bandRow = document.createElement('tr');
      bandRow.className = codigo === 'BALCAO' ? 'band-row band-dolar' : 'band-row band-cafe';
      bandRow.innerHTML = `<td colspan="13">${bandLabel(codigo, pracaNome)}</td>`;
      tbody.appendChild(bandRow);

      const sorted = pracaItems.sort((a, b) => a.vencimento_label.localeCompare(b.vencimento_label));
      for (const q of sorted) {
        const decimals = codigo === 'BALCAO' ? 4 : 2;
        const tr = document.createElement('tr');
        tr.dataset.instrumentoId = q.instrumento_id;
        tr.innerHTML = `
          <td class="col-venc">${q.vencimento_label}</td>
          <td class="preco-ultimo">${formatNumber(q.preco_ultimo, decimals)}</td>
          <td class="${varClass(q.variacao_pct)}">${formatNumber(q.variacao, decimals)}</td>
          <td class="${varClass(q.variacao_pct)}">${q.variacao_pct != null ? formatNumber(q.variacao_pct, 2) + '%' : ''}</td>
          <td>${formatNumber(q.preco_abertura, decimals)}</td>
          <td>${formatNumber(q.preco_maximo, decimals)}</td>
          <td>${formatNumber(q.preco_minimo, decimals)}</td>
          <td>${formatNumber(q.preco_fechamento, decimals)}</td>
          <td>${formatNumber(q.preco_compra, decimals)}</td>
          <td>${formatNumber(q.preco_venda, decimals)}</td>
          <td>${formatNumber(q.contratos_abertos, 0)}</td>
          <td>${formatNumber(q.contratos_negociados, 0)}</td>
          <td>${formatNumber(q.preco_ajuste, decimals)}</td>
        `;
        tbody.appendChild(tr);
      }
    }
  }

  // ----- WebSocket em tempo real -----
  const statusEl = document.getElementById('connection-status');
  const liveDot = document.getElementById('live-dot');
  let ws = null;
  let reconnectDelay = 1000;
  let pingInterval = null;

  function setStatus(state) {
    statusEl.classList.remove('status-connecting', 'status-online', 'status-offline');
    liveDot.classList.toggle('live-dot-online', state === 'online');
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
