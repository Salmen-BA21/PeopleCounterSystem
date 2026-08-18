/**
 * People Counter Frontend
 * Multi-feed live dashboard: per-source WebSocket streams, grid tiles,
 * focus overlay for counting-line drawing, EN/FR i18n, light/dark theme.
 */

(function () {
  'use strict';

  // Shared elements
  const feedsGrid = document.getElementById('feeds-grid');
  const feedsEmpty = document.getElementById('feeds-empty');

  const connectionBadge = document.getElementById('connection-badge');
  const connectionText = document.getElementById('connection-text');

  const statInVal = document.getElementById('stat-in-val');
  const statOutVal = document.getElementById('stat-out-val');
  const statCurrentVal = document.getElementById('stat-current-val');

  // Focus overlay elements
  const focusVeil = document.getElementById('focus-veil');
  const focusName = document.getElementById('focus-name');
  const focusVideo = document.getElementById('focus-video');
  const focusOverlay = document.getElementById('focus-overlay');
  const focusStage = document.getElementById('focus-stage');
  const focusVideoCtx = focusVideo.getContext('2d');
  const focusOverlayCtx = focusOverlay.getContext('2d');

  const lastCrossingTag = document.getElementById('last-crossing-tag');
  const lastCrossingText = document.getElementById('last-crossing-text');

  const btnDrawToggle = document.getElementById('btn-draw-toggle');
  const drawActions = document.getElementById('draw-actions');
  const btnDrawConfirm = document.getElementById('btn-draw-confirm');
  const btnDrawReset = document.getElementById('btn-draw-reset');
  const btnDrawCancel = document.getElementById('btn-draw-cancel');
  const drawBanner = document.getElementById('draw-banner');
  const drawPrompt = document.getElementById('draw-prompt');

  const btnResetCounts = document.getElementById('btn-reset-counts');
  const btnFocusClose = document.getElementById('btn-focus-close');

  const cfgLine = document.getElementById('cfg-line');
  const dirHint = document.getElementById('dir-hint');

  const videoListEl = document.getElementById('video-list');
  const btnTriggerUpload = document.getElementById('btn-trigger-upload');
  const inputVideoFile = document.getElementById('input-video-file');
  const uploadProgressMsg = document.getElementById('upload-progress-msg');

  const segButtons = document.querySelectorAll('.seg-btn');
  const feedFile = document.getElementById('feed-file');
  const feedCamera = document.getElementById('feed-camera');
  const btnDiscover = document.getElementById('btn-discover');
  const cameraStatus = document.getElementById('camera-status');
  const cameraList = document.getElementById('camera-list');
  const cameraCreds = document.getElementById('camera-creds');
  const inputCameraUser = document.getElementById('input-camera-user');
  const inputCameraPass = document.getElementById('input-camera-pass');
  const btnCameraProfiles = document.getElementById('btn-camera-profiles');
  const profileList = document.getElementById('profile-list');
  const btnCameraConnect = document.getElementById('btn-camera-connect');

  const reportsList = document.getElementById('reports-list');
  const btnReportsRefresh = document.getElementById('btn-reports-refresh');

  const tileTpl = document.getElementById('feed-tile-tpl');

  function set(el, value) {
    if (el) el.textContent = value;
  }

  const I18N = {
    en: {
      title: 'People Counter — Live visitor counting',
      brandSub: 'Live visitor counts for your space',
      live: 'Live',
      reconnecting: 'Reconnecting…',
      connecting: 'Connecting…',
      peopleIn: 'People in',
      peopleOut: 'People out',
      insideNow: 'Inside right now',
      entered: 'entered',
      left: 'left',
      inSpace: 'people in the space',
      visitorCounted: 'Visitor counted',
      setLine: 'Set counting line',
      saveLine: 'Save line',
      startOver: 'Start over',
      cancel: 'Cancel',
      resetCounters: 'Reset counters',
      videoFiles: 'Video files',
      ipCamera: 'IP camera',
      uploadVideo: 'Upload video',
      uploading: 'Uploading video…',
      uploadingFile: 'Uploading {0}...',
      uploadFailed: 'Upload failed: {0}',
      uploaded: 'Uploaded — now counting',
      findCameras: 'Find cameras',
      cameraUsername: 'Camera username',
      cameraPassword: 'Camera password',
      loadProfiles: 'Load profiles',
      connect: 'Connect',
      cameraHint: 'Cameras are found automatically. Use the credentials you set on the camera itself.',
      countingSettings: 'Counting settings',
      whichWay: 'Which way do people move when they enter?',
      topToBottom: 'Top to bottom',
      bottomToTop: 'Bottom to top',
      leftToRight: 'Left to right',
      rightToLeft: 'Right to left',
      noLineYet: 'No line yet',
      lineIsSet: 'Line is set',
      saved: 'Saved',
      setLineFirst: 'Set a counting line first.',
      couldNotSave: 'Could not save. Try again.',
      step1: 'Step 1: click one end of where people cross',
      step2: 'Step 2: click the other end to finish the line',
      lineLooksGood: 'Line looks good — tap Save line to keep it.',
      saving: 'Saving…',
      failedSaveLine: 'Failed to save line: {0}',
      scanning: 'Scanning…',
      lookingForCameras: 'Looking for cameras on the network…',
      noCameras: 'No cameras found. Check they are powered on and on the same network.',
      couldNotScan: 'Could not scan: {0}',
      camera: 'Camera',
      loading: 'Loading…',
      streamsOn: 'Streams on {0}: {1}',
      couldNotLoadProfiles: 'Could not load profiles: {0}',
      enterCreds: 'Enter the camera username and password.',
      connecting: 'Connecting…',
      connectedTo: 'Connected to {0}',
      couldNotConnect: 'Could not connect: {0}',
      addFeed: 'Add a feed',
      noFeeds: 'No feeds yet',
      addFirstFeed: 'Add a video or camera from the panel to start counting.',
      noVideos: 'No videos on the server yet.',
      add: 'Add',
      added: 'Added',
      removeFeed: 'Remove feed',
      removeFailed: 'Could not remove feed: {0}',
      backToAll: 'Back to all feeds',
      reports: 'Reports',
      refresh: 'Refresh',
      download: 'Download',
      reportsEmpty: 'No reports yet. Daily totals appear here.',
      reportMeta: '{0} in · {1} out',
      modelLabel: 'Counting precision',
      modelQuick: 'Quick',
      modelPrecise: 'Precise',
      modelFailed: 'Could not switch precision: {0}',
      stopFeed: 'Stop',
      playFeed: 'Play',
      stopped: 'Stopped',
      runFailed: 'Could not stop or play feed: {0}',
    },
    fr: {
      title: 'Compteur de personnes — Comptage de visiteurs en direct',
      brandSub: 'Comptage en direct des visiteurs de votre espace',
      live: 'En direct',
      reconnecting: 'Reconnexion…',
      connecting: 'Connexion…',
      peopleIn: 'Entrées',
      peopleOut: 'Sorties',
      insideNow: 'Sur place actuellement',
      entered: 'entrées',
      left: 'sorties',
      inSpace: 'personnes dans l’espace',
      visitorCounted: 'Visiteur compté',
      setLine: 'Définir la ligne',
      saveLine: 'Enregistrer la ligne',
      startOver: 'Recommencer',
      cancel: 'Annuler',
      resetCounters: 'Remettre à zéro',
      videoFiles: 'Fichiers vidéo',
      ipCamera: 'Caméra IP',
      uploadVideo: 'Importer une vidéo',
      uploading: 'Import de la vidéo…',
      uploadingFile: 'Import de {0}...',
      uploadFailed: 'Échec de l’import : {0}',
      uploaded: 'Importé — comptage en cours',
      findCameras: 'Trouver les caméras',
      cameraUsername: 'Identifiant de la caméra',
      cameraPassword: 'Mot de passe de la caméra',
      loadProfiles: 'Charger les profils',
      connect: 'Se connecter',
      cameraHint: 'Les caméras sont trouvées automatiquement. Utilisez les identifiants définis sur la caméra elle-même.',
      countingSettings: 'Réglages de comptage',
      whichWay: 'Dans quel sens les personnes entrent-elles ?',
      topToBottom: 'Du haut vers le bas',
      bottomToTop: 'Du bas vers le haut',
      leftToRight: 'De gauche à droite',
      rightToLeft: 'De droite à gauche',
      noLineYet: 'Aucune ligne',
      lineIsSet: 'Ligne définie',
      saved: 'Enregistré',
      setLineFirst: 'Définissez d’abord une ligne de comptage.',
      couldNotSave: 'Impossible d’enregistrer. Réessayez.',
      step1: 'Étape 1 : cliquez sur une extrémité de l’endroit où les personnes passent',
      step2: 'Étape 2 : cliquez sur l’autre extrémité pour terminer la ligne',
      lineLooksGood: 'La ligne semble correcte — appuyez sur Enregistrer la ligne.',
      saving: 'Enregistrement…',
      failedSaveLine: 'Échec de l’enregistrement de la ligne : {0}',
      scanning: 'Recherche…',
      lookingForCameras: 'Recherche de caméras sur le réseau…',
      noCameras: 'Aucune caméra trouvée. Vérifiez qu’elles sont allumées et sur le même réseau.',
      couldNotScan: 'Recherche impossible : {0}',
      camera: 'Caméra',
      loading: 'Chargement…',
      streamsOn: 'Flux sur {0} : {1}',
      couldNotLoadProfiles: 'Impossible de charger les profils : {0}',
      enterCreds: 'Saisissez l’identifiant et le mot de passe de la caméra.',
      connecting: 'Connexion…',
      connectedTo: 'Connecté à {0}',
      couldNotConnect: 'Connexion impossible : {0}',
      addFeed: 'Ajouter un flux',
      noFeeds: 'Aucun flux',
      addFirstFeed: 'Ajoutez une vidéo ou une caméra depuis le panneau pour commencer le comptage.',
      noVideos: 'Aucune vidéo sur le serveur pour l’instant.',
      add: 'Ajouter',
      added: 'Ajouté',
      removeFeed: 'Retirer le flux',
      removeFailed: 'Impossible de retirer le flux : {0}',
      backToAll: 'Retour à tous les flux',
      reports: 'Rapports',
      refresh: 'Actualiser',
      download: 'Télécharger',
      reportsEmpty: 'Aucun rapport pour l’instant. Les totaux quotidiens apparaîtront ici.',
      reportMeta: '{0} entrées · {1} sorties',
      modelLabel: 'Précision du comptage',
      modelQuick: 'Rapide',
      modelPrecise: 'Précise',
      modelFailed: 'Impossible de changer la précision : {0}',
      stopFeed: 'Arrêter',
      playFeed: 'Lire',
      stopped: 'Arrêté',
      runFailed: 'Impossible d\'arrêter ou de lire le flux : {0}',
    },
  };

  let currentLang = 'en';

  function t(key, ...params) {
    const str = (I18N[currentLang] && I18N[currentLang][key]) || I18N.en[key] || key;
    return params.reduce((acc, p, i) => acc.replace(`{${i}}`, p), str);
  }

  // ---- State ----
  const tiles = new Map(); // source_id -> tile
  let focusedTile = null;
  let dirHintTimer = null;
  let cameraStatusTimer = null;

  // ---- i18n ----
  function applyLang() {
    document.documentElement.lang = currentLang;
    const toggle = document.getElementById('lang-toggle');
    if (toggle) toggle.textContent = currentLang === 'en' ? 'FR' : 'EN';
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      set(el, t(el.dataset.i18n));
    });
    document.title = t('title');
    updateFocusChrome();
    updateConnectionStatus();
  }

  function setupLang() {
    const saved = localStorage.getItem('lang');
    currentLang = saved || (navigator.language.toLowerCase().startsWith('fr') ? 'fr' : 'en');
    applyLang();
    const toggle = document.getElementById('lang-toggle');
    if (toggle) {
      toggle.addEventListener('click', () => {
        currentLang = currentLang === 'en' ? 'fr' : 'en';
        localStorage.setItem('lang', currentLang);
        applyLang();
      });
    }
  }

  // ---- Theme ----
  function setupTheme() {
    const root = document.documentElement;
    const saved = localStorage.getItem('theme');
    const initial = saved || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    root.setAttribute('data-theme', initial);
    const toggle = document.getElementById('theme-toggle');
    if (toggle) {
      toggle.addEventListener('click', () => {
        const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        root.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
      });
    }
  }

  // ---- Master metrics ----
  function recomputeTotals() {
    let inCount = 0;
    let outCount = 0;
    let currentCount = 0;
    tiles.forEach((tile) => {
      inCount += tile.counts.in;
      outCount += tile.counts.out;
      currentCount += tile.counts.current;
    });
    set(statInVal, inCount);
    set(statOutVal, outCount);
    set(statCurrentVal, currentCount);
  }

  // ---- Connection status ----
  function updateConnectionStatus() {
    const total = tiles.size;
    const connected = [...tiles.values()].filter((t) => t.videoOpen && t.countsOpen).length;
    if (total > 0 && connected === total) {
      connectionBadge.className = 'status status-live';
      set(connectionText, t('live'));
    } else if (connected > 0) {
      connectionBadge.className = 'status';
      set(connectionText, t('reconnecting'));
    } else {
      connectionBadge.className = 'status';
      set(connectionText, t('connecting'));
    }
  }

  function getWsUrl(endpoint) {
    const loc = window.location;
    const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = loc.host || 'localhost:8000';
    return `${proto}//${host}${endpoint}`;
  }

  // ---- Focus overlay chrome ----
  function updateFocusChrome() {
    if (!focusedTile) return;
    const tile = focusedTile;
    set(cfgLine, tile.line ? t('lineIsSet') : t('noLineYet'));
    cfgLine.classList.toggle('ok', !!tile.line);
    setActiveDir(tile.enteringDirection);
    setActiveModel(tile.model);
    const drawing = tile.draw.isDrawing;
    if (drawing) {
      set(drawPrompt, !tile.draw.p1 ? t('step1') : (!tile.draw.p2 ? t('step2') : t('lineLooksGood')));
    }
  }

function setActiveDir(value) {
    document.querySelectorAll('.dir-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.value === value);
    });
  }

  function setActiveModel(value) {
    document.querySelectorAll('.model-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.model === value);
    });
  }

  function showDirHint(msg) {
    if (!dirHint) return;
    dirHint.textContent = msg;
    dirHint.classList.remove('hidden');
    clearTimeout(dirHintTimer);
    dirHintTimer = setTimeout(() => dirHint.classList.add('hidden'), 2500);
  }

  // ---- Tile factory ----
  function createTile(src) {
    const el = tileTpl.content.firstElementChild.cloneNode(true);
    const tile = {
      id: src.id,
      name: src.name || src.id,
      source: src.source || '',
      counts: { in: 0, out: 0, current: 0 },
      line: src.line || null,
      enteringDirection: src.entering_direction || null,
      model: src.model || 'quick',
      running: !!src.running,
      videoOpen: false,
      countsOpen: false,
      draw: { isDrawing: false, p1: null, p2: null, hover: null },
      crossingTimer: null,
      retry: 0,
      el,
      videoCanvas: el.querySelector('.tile-video'),
      videoCtx: null,
      nameEl: el.querySelector('.tile-name'),
      statusEl: el.querySelector('.tile-status'),
      statusTextEl: el.querySelector('.tile-status-text'),
      statVals: [...el.querySelectorAll('.tile-stat-val')],
    };
    tile.videoCtx = tile.videoCanvas.getContext('2d');

    tile.nameEl.textContent = tile.name;
    set(tile.statusTextEl, tile.running ? t('live') : t('connecting'));

    const removeBtn = el.querySelector('.tile-remove');
    removeBtn.setAttribute('aria-label', t('removeFeed'));
    removeBtn.title = t('removeFeed');
    removeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      removeTile(tile);
    });
    const lineBtn = el.querySelector('.tile-line');
    lineBtn.setAttribute('aria-label', t('setLine'));
    lineBtn.title = t('setLine');
    lineBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      openFocus(tile);
      startDrawingMode();
    });
    const playBtn = el.querySelector('.tile-play');
    const playBtnIcons = { play: playBtn.querySelector('.icon-play'), pause: playBtn.querySelector('.icon-pause') };
    function renderPlayBtn() {
      playBtnIcons.play.classList.toggle('hidden', tile.running);
      playBtnIcons.pause.classList.toggle('hidden', !tile.running);
      const label = tile.running ? t('stopFeed') : t('playFeed');
      playBtn.setAttribute('aria-label', label);
      playBtn.title = label;
    }
    playBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        const resp = await fetch(`/api/sources/${tile.id}/running`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ running: !tile.running }),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        tile.running = !tile.running;
        renderPlayBtn();
        set(tile.statusTextEl, tile.running ? (tile.videoOpen && tile.countsOpen ? t('live') : t('connecting')) : t('stopped'));
        updateConnectionStatus();
      } catch (err) {
        alert(t('runFailed', err.message));
      }
    });
    renderPlayBtn();
    el.addEventListener('click', () => openFocus(tile));
    const stage = el.querySelector('.feed-tile-stage');
    stage.tabIndex = 0;
    stage.setAttribute('role', 'button');
    stage.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openFocus(tile);
      }
    });

    feedsGrid.appendChild(el);
    tiles.set(tile.id, tile);

    connectTileVideoSocket(tile);
    connectTileCountsSocket(tile);
    updateEmptyState();
    reloadVideoList();
    return tile;
  }

  function destroyTile(tile) {
    if (tile.wsVideo) tile.wsVideo.close();
    if (tile.wsCounts) tile.wsCounts.close();
    if (focusedTile === tile) closeFocus();
    tile.el.remove();
    tiles.delete(tile.id);
    recomputeTotals();
    updateEmptyState();
    updateConnectionStatus();
    reloadVideoList();
  }

  async function removeTile(tile) {
    try {
      const resp = await fetch(`/api/sources/${tile.id}`, { method: 'DELETE' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      destroyTile(tile);
    } catch (err) {
      alert(t('removeFailed', err.message));
    }
  }

  function updateEmptyState() {
    feedsEmpty.classList.toggle('hidden', tiles.size > 0);
  }

  // ---- Tile sockets ----
  function scheduleReconnect(tile, connectFn) {
    const delay = Math.min(1500 * 2 ** tile.retry, 30000);
    tile.retry += 1;
    setTimeout(() => {
      if (tiles.has(tile.id)) connectFn(tile);
    }, delay);
  }

  function connectTileVideoSocket(tile) {
    const url = getWsUrl(`/ws/video/${tile.id}`);
    tile.wsVideo = new WebSocket(url);
    tile.wsVideo.binaryType = 'arraybuffer';

    tile.wsVideo.onopen = () => {
      tile.videoOpen = true;
      tile.retry = 0;
      updateConnectionStatus();
    };

    tile.wsVideo.onmessage = async (event) => {
      try {
        const buffer = event.data;
        if (buffer.byteLength < 8) return;
        const jpegBlob = new Blob([buffer.slice(8)], { type: 'image/jpeg' });
        const bitmap = await createImageBitmap(jpegBlob);

        if (tile.videoCanvas.width !== bitmap.width || tile.videoCanvas.height !== bitmap.height) {
          tile.videoCanvas.width = bitmap.width;
          tile.videoCanvas.height = bitmap.height;
          focusVideo.width = bitmap.width;
          focusVideo.height = bitmap.height;
          focusOverlay.width = bitmap.width;
          focusOverlay.height = bitmap.height;
        }

        const target = focusedTile === tile ? focusVideoCtx : tile.videoCtx;
        target.drawImage(bitmap, 0, 0);
        bitmap.close();
        if (focusedTile === tile && !tile.draw.isDrawing && tile.line) {
          renderSavedLine(tile);
        }
      } catch (err) {
        console.error('Frame decode error:', err);
      }
    };

    tile.wsVideo.onclose = () => {
      tile.videoOpen = false;
      updateConnectionStatus();
      scheduleReconnect(tile, connectTileVideoSocket);
    };

    tile.wsVideo.onerror = () => tile.wsVideo.close();
  }

  function connectTileCountsSocket(tile) {
    const url = getWsUrl(`/ws/counts/${tile.id}`);
    tile.wsCounts = new WebSocket(url);

    tile.wsCounts.onopen = () => {
      tile.countsOpen = true;
      tile.retry = 0;
      updateConnectionStatus();
    };

    tile.wsCounts.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        tile.counts.in = data.in ?? 0;
        tile.counts.out = data.out ?? 0;
        tile.counts.current = data.current ?? 0;
        tile.statVals[0].textContent = tile.counts.in;
        tile.statVals[1].textContent = tile.counts.out;
        tile.statVals[2].textContent = tile.counts.current;
        recomputeTotals();

        if (data.line) tile.line = data.line;
        if (data.entering_direction) tile.enteringDirection = data.entering_direction;

        if (data.last_crossing && data.last_crossing.trim() !== '' && focusedTile === tile) {
          set(lastCrossingText, t('visitorCounted'));
          lastCrossingTag.classList.remove('hidden');
          if (tile.crossingTimer) clearTimeout(tile.crossingTimer);
          tile.crossingTimer = setTimeout(() => lastCrossingTag.classList.add('hidden'), 3000);
        }

        if (focusedTile === tile) {
          updateFocusChrome();
          if (!tile.draw.isDrawing && tile.line) renderSavedLine(tile);
        }
      } catch (err) {
        console.error('Counts parse error:', err);
      }
    };

    tile.wsCounts.onclose = () => {
      tile.countsOpen = false;
      updateConnectionStatus();
      scheduleReconnect(tile, connectTileCountsSocket);
    };

    tile.wsCounts.onerror = () => tile.wsCounts.close();
  }

  // ---- Focus overlay ----
  function openFocus(tile) {
    if (focusedTile === tile) return;
    if (focusedTile) closeFocus();
    focusedTile = tile;
    set(focusName, tile.name);
    focusVeil.classList.remove('hidden');
    set(tile.statusTextEl, tile.videoOpen && tile.countsOpen ? t('live') : t('connecting'));
    updateFocusChrome();
    if (tile.line) renderSavedLine(tile);
  }

  function closeFocus() {
    if (!focusedTile) return;
    stopDrawingMode();
    focusedTile = null;
    focusVeil.classList.add('hidden');
    focusOverlayCtx.clearRect(0, 0, focusOverlay.width, focusOverlay.height);
  }

  // ---- Line drawing ----
  function startDrawingMode() {
    if (!focusedTile) return;
    const tile = focusedTile;
    tile.draw.isDrawing = true;
    resetDrawingPoints();
    focusStage.classList.add('drawing-active');
    drawActions.classList.remove('hidden');
    drawBanner.classList.remove('hidden');
    btnDrawToggle.classList.add('hidden');
    set(drawPrompt, t('step1'));
  }

  function stopDrawingMode() {
    if (!focusedTile) return;
    const tile = focusedTile;
    tile.draw.isDrawing = false;
    resetDrawingPoints();
    focusStage.classList.remove('drawing-active');
    drawActions.classList.add('hidden');
    drawBanner.classList.add('hidden');
    btnDrawToggle.classList.remove('hidden');
    focusOverlayCtx.clearRect(0, 0, focusOverlay.width, focusOverlay.height);
    if (tile.line) renderSavedLine(tile);
  }

  function resetDrawingPoints() {
    if (!focusedTile) return;
    const tile = focusedTile;
    tile.draw.p1 = null;
    tile.draw.p2 = null;
    tile.draw.hover = null;
    btnDrawConfirm.disabled = true;
    if (tile.draw.isDrawing) set(drawPrompt, t('step1'));
    clearOverlay();
  }

  function getCanvasCoords(e) {
    const rect = focusOverlay.getBoundingClientRect();
    const scaleX = focusOverlay.width / rect.width;
    const scaleY = focusOverlay.height / rect.height;
    return {
      x: Math.round((e.clientX - rect.left) * scaleX),
      y: Math.round((e.clientY - rect.top) * scaleY),
    };
  }

  function handleCanvasClick(e) {
    if (!focusedTile || !focusedTile.draw.isDrawing) return;
    const tile = focusedTile;
    const coords = getCanvasCoords(e);

    if (!tile.draw.p1) {
      tile.draw.p1 = coords;
      set(drawPrompt, t('step2'));
      renderOverlay();
    } else if (!tile.draw.p2) {
      tile.draw.p2 = coords;
      btnDrawConfirm.disabled = false;
      set(drawPrompt, t('lineLooksGood'));
      renderOverlay();
    }
  }

  function handleCanvasMouseMove(e) {
    if (!focusedTile || !focusedTile.draw.isDrawing) return;
    focusedTile.draw.hover = getCanvasCoords(e);
    renderOverlay();
  }

  function clearOverlay() {
    focusOverlayCtx.clearRect(0, 0, focusOverlay.width, focusOverlay.height);
  }

  function renderOverlay() {
    clearOverlay();
    if (!focusedTile || !focusedTile.draw.isDrawing) return;
    const tile = focusedTile;

    if (tile.draw.p1) {
      drawMarker(tile.draw.p1.x, tile.draw.p1.y, '#10b981', 'P1');
      const endPoint = tile.draw.p2 || tile.draw.hover;
      if (endPoint) {
        focusOverlayCtx.beginPath();
        focusOverlayCtx.strokeStyle = '#d97706';
        focusOverlayCtx.lineWidth = 2.5;
        focusOverlayCtx.setLineDash(tile.draw.p2 ? [] : [6, 4]);
        focusOverlayCtx.moveTo(tile.draw.p1.x, tile.draw.p1.y);
        focusOverlayCtx.lineTo(endPoint.x, endPoint.y);
        focusOverlayCtx.stroke();
        focusOverlayCtx.setLineDash([]);
      }
    }

    if (tile.draw.p2) {
      drawMarker(tile.draw.p2.x, tile.draw.p2.y, '#d97706', 'P2');
    }
  }

  function drawMarker(x, y, color, label) {
    focusOverlayCtx.beginPath();
    focusOverlayCtx.arc(x, y, 7, 0, Math.PI * 2);
    focusOverlayCtx.fillStyle = color;
    focusOverlayCtx.fill();
    focusOverlayCtx.strokeStyle = '#ffffff';
    focusOverlayCtx.lineWidth = 2;
    focusOverlayCtx.stroke();

    focusOverlayCtx.font = 'bold 12px Plus Jakarta Sans, sans-serif';
    focusOverlayCtx.fillStyle = '#ffffff';
    focusOverlayCtx.fillText(`${label} (${x}, ${y})`, x + 12, y - 8);
  }

  function renderSavedLine(tile) {
    if (!tile.line) return;
    clearOverlay();
    const [x1, y1, x2, y2] = tile.line;
    focusOverlayCtx.beginPath();
    focusOverlayCtx.strokeStyle = '#d97706';
    focusOverlayCtx.lineWidth = 2.5;
    focusOverlayCtx.moveTo(x1, y1);
    focusOverlayCtx.lineTo(x2, y2);
    focusOverlayCtx.stroke();
  }

  async function confirmLine() {
    if (!focusedTile) return;
    const tile = focusedTile;
    if (!tile.draw.p1 || !tile.draw.p2) return;

    try {
      btnDrawConfirm.disabled = true;
      btnDrawConfirm.textContent = t('saving');

      const payload = {
        x1: tile.draw.p1.x,
        y1: tile.draw.p1.y,
        x2: tile.draw.p2.x,
        y2: tile.draw.p2.y,
      };

      const resp = await fetch(`/api/sources/${tile.id}/line`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const result = await resp.json();
      tile.line = result.line;
      tile.enteringDirection = result.entering_direction;
      stopDrawingMode();
    } catch (err) {
      alert(t('failedSaveLine', err.message));
    } finally {
      btnDrawConfirm.textContent = t('saveLine');
      btnDrawConfirm.disabled = false;
    }
  }

  // ---- Focus events ----
  function setupFocusEvents() {
    btnDrawToggle.addEventListener('click', () => {
      if (focusedTile && focusedTile.draw.isDrawing) {
        stopDrawingMode();
      } else {
        startDrawingMode();
      }
    });

    btnDrawReset.addEventListener('click', resetDrawingPoints);
    btnDrawCancel.addEventListener('click', stopDrawingMode);
    btnDrawConfirm.addEventListener('click', confirmLine);
    btnFocusClose.addEventListener('click', closeFocus);
    focusVeil.addEventListener('click', (e) => {
      if (e.target === focusVeil) closeFocus();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && focusedTile) closeFocus();
    });

    focusOverlay.addEventListener('click', handleCanvasClick);
    focusOverlay.addEventListener('mousemove', handleCanvasMouseMove);

    btnResetCounts.addEventListener('click', async () => {
      if (!focusedTile) return;
      try {
        const resp = await fetch(`/api/sources/${focusedTile.id}/reset`, { method: 'POST' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      } catch (err) {
        console.error('Failed to reset counts:', err);
      }
    });

    document.querySelectorAll('.dir-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!focusedTile) return;
        const selected = btn.dataset.value || null;
        if (!focusedTile.line) {
          showDirHint(t('setLineFirst'));
          return;
        }

        try {
          const resp = await fetch(`/api/sources/${focusedTile.id}/line`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              x1: focusedTile.line[0],
              y1: focusedTile.line[1],
              x2: focusedTile.line[2],
              y2: focusedTile.line[3],
              entering_direction: selected,
            }),
          });
          if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
          const result = await resp.json();
          focusedTile.enteringDirection = result.entering_direction;
          setActiveDir(result.entering_direction);
          showDirHint(t('saved'));
        } catch (err) {
          showDirHint(t('couldNotSave'));
        }
      });
    });

    document.querySelectorAll('.model-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!focusedTile || btn.dataset.model === focusedTile.model) return;
        const model = btn.dataset.model;
        document.querySelectorAll('.model-btn').forEach((b) => (b.disabled = true));
        try {
          const resp = await fetch(`/api/sources/${focusedTile.id}/model`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model }),
          });
          if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
          const result = await resp.json();
          focusedTile.model = result.model;
          setActiveModel(result.model);
        } catch (err) {
          alert(t('modelFailed', err.message));
        } finally {
          document.querySelectorAll('.model-btn').forEach((b) => (b.disabled = false));
        }
      });
    });
  }

  // ---- Add-feed sidebar ----
  function renderVideoList(videos) {
    videoListEl.innerHTML = '';
    if (!videos.length) {
      const note = document.createElement('p');
      note.className = 'feed-hint';
      note.textContent = t('noVideos');
      videoListEl.appendChild(note);
      return;
    }

    const addedNames = new Set(
      [...tiles.values()].map((tile) => tile.source.split(/[\\/]/).pop())
    );

    videos.forEach((vid) => {
      const name = vid.split(/[\\/]/).pop();
      const row = document.createElement('div');
      row.className = 'video-row';

      const label = document.createElement('span');
      label.className = 'video-name';
      label.textContent = name;

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn video-add';
      if (addedNames.has(name)) {
        btn.disabled = true;
        btn.textContent = t('added');
      } else {
        btn.textContent = t('add');
        btn.addEventListener('click', async () => {
          btn.disabled = true;
          btn.textContent = t('loading');
          try {
            const resp = await fetch('/api/sources', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ source: vid, name }),
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const src = await resp.json();
            createTile(src);
          } catch (err) {
            alert(err.message);
            btn.disabled = false;
            btn.textContent = t('add');
          }
        });
      }

      row.appendChild(label);
      row.appendChild(btn);
      videoListEl.appendChild(row);
    });
  }

  async function reloadVideoList() {
    try {
      const resp = await fetch('/api/videos');
      if (!resp.ok) return;
      const data = await resp.json();
      renderVideoList(data.videos || []);
    } catch (err) {
      console.error('Failed to load video list:', err);
    }
  }

  // ---- Reports ----
  function renderReports(reports) {
    reportsList.innerHTML = '';
    if (!reports.length) {
      const note = document.createElement('p');
      note.className = 'feed-hint';
      note.textContent = t('reportsEmpty');
      reportsList.appendChild(note);
      return;
    }

    reports.forEach((rep) => {
      const row = document.createElement('div');
      row.className = 'video-row';

      const info = document.createElement('div');
      info.className = 'report-info';

      const name = document.createElement('span');
      name.className = 'video-name';
      name.textContent = `${rep.date} — ${rep.name}`;

      const meta = document.createElement('span');
      meta.className = 'report-meta';
      meta.textContent = t('reportMeta', rep.in, rep.out);

      info.appendChild(name);
      info.appendChild(meta);

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn video-add';
      btn.textContent = t('download');
      btn.addEventListener('click', () => {
        window.location.href = `/api/reports/${encodeURIComponent(rep.filename)}`;
      });

      row.appendChild(info);
      row.appendChild(btn);
      reportsList.appendChild(row);
    });
  }

  async function loadReports() {
    try {
      const resp = await fetch('/api/reports');
      if (!resp.ok) return;
      const data = await resp.json();
      renderReports(data.reports || []);
    } catch (err) {
      console.error('Failed to load reports:', err);
    }
  }

  function setupFeedEvents() {
    segButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        segButtons.forEach((b) => b.classList.toggle('active', b === btn));
        const mode = btn.dataset.mode;
        feedFile.classList.toggle('hidden', mode !== 'file');
        feedCamera.classList.toggle('hidden', mode !== 'camera');
      });
    });

    btnTriggerUpload.addEventListener('click', () => inputVideoFile.click());
    if (btnReportsRefresh) btnReportsRefresh.addEventListener('click', loadReports);

    inputVideoFile.addEventListener('change', async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;

      const formData = new FormData();
      formData.append('file', file);

      try {
        uploadProgressMsg.classList.remove('hidden');
        uploadProgressMsg.textContent = t('uploadingFile', file.name);
        btnTriggerUpload.disabled = true;

        const resp = await fetch('/api/upload', { method: 'POST', body: formData });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const result = await resp.json();

        createTile(result.source);
        uploadProgressMsg.textContent = t('uploaded');
        setTimeout(() => uploadProgressMsg.classList.add('hidden'), 2500);
      } catch (err) {
        alert(t('uploadFailed', err.message));
        uploadProgressMsg.classList.add('hidden');
      } finally {
        btnTriggerUpload.disabled = false;
        inputVideoFile.value = '';
      }
    });

    btnDiscover.addEventListener('click', async () => {
      btnDiscover.disabled = true;
      btnDiscover.textContent = t('scanning');
      setCameraStatus(t('lookingForCameras'));
      cameraList.classList.add('hidden');
      cameraList.innerHTML = '';
      cameraCreds.classList.add('hidden');
      profileList.classList.add('hidden');
      profileList.innerHTML = '';
      selectedCamera = null;
      selectedProfile = null;
      try {
        const resp = await fetch('/api/cameras');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        const devices = data.devices || [];
        if (!devices.length) {
          setCameraStatus(t('noCameras'));
          return;
        }
        cameraStatus.classList.add('hidden');
        renderCameras(devices);
      } catch (err) {
        setCameraStatus(t('couldNotScan', err.message), true);
      } finally {
        btnDiscover.disabled = false;
        btnDiscover.textContent = t('findCameras');
      }
    });

    btnCameraProfiles.addEventListener('click', async () => {
      if (!selectedCamera) return;
      const username = inputCameraUser.value.trim();
      const password = inputCameraPass.value;
      if (!username || !password) {
        setCameraStatus(t('enterCreds'), true);
        return;
      }
      btnCameraProfiles.disabled = true;
      btnCameraProfiles.textContent = t('loading');
      try {
        const resp = await fetch('/api/cameras/profiles', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            host: selectedCamera.host,
            port: selectedCamera.port,
            username,
            password,
          }),
        });
        if (!resp.ok) {
          const data = await resp.json().catch(() => null);
          throw new Error(data?.detail || `HTTP ${resp.status}`);
        }
        const data = await resp.json();
        renderProfiles(data.profiles || []);
        setCameraStatus(t('streamsOn', selectedCamera.host, (data.profiles || []).length), true);
      } catch (err) {
        setCameraStatus(t('couldNotLoadProfiles', err.message), true);
      } finally {
        btnCameraProfiles.disabled = false;
        btnCameraProfiles.textContent = t('loadProfiles');
      }
    });

    btnCameraConnect.addEventListener('click', async () => {
      if (!selectedCamera || !selectedProfile) return;
      const username = inputCameraUser.value.trim();
      const password = inputCameraPass.value;
      if (!username || !password) {
        setCameraStatus(t('enterCreds'), true);
        return;
      }
      btnCameraConnect.disabled = true;
      btnCameraConnect.textContent = t('connecting');
      try {
        const resp = await fetch('/api/cameras/connect', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            host: selectedCamera.host,
            port: selectedCamera.port,
            username,
            password,
            profile_token: selectedProfile.token,
          }),
        });
        if (!resp.ok) {
          const data = await resp.json().catch(() => null);
          throw new Error(data?.detail || `HTTP ${resp.status}`);
        }
        const data = await resp.json();
        createTile(data.source);
        setCameraStatus(t('connectedTo', data.host), true);
        cameraCreds.classList.add('hidden');
        cameraList.querySelectorAll('.camera-chip').forEach((c) => c.classList.remove('active'));
        selectedCamera = null;
        selectedProfile = null;
        inputCameraUser.value = '';
        inputCameraPass.value = '';
      } catch (err) {
        setCameraStatus(t('couldNotConnect', err.message), true);
      } finally {
        btnCameraConnect.disabled = false;
        btnCameraConnect.textContent = t('connect');
      }
    });
  }

  let selectedCamera = null;
  let selectedProfile = null;

  function setCameraStatus(msg, transient) {
    if (!cameraStatus) return;
    cameraStatus.textContent = msg;
    cameraStatus.classList.remove('hidden');
    clearTimeout(cameraStatusTimer);
    if (transient) {
      cameraStatusTimer = setTimeout(() => cameraStatus.classList.add('hidden'), 3500);
    }
  }

  function renderCameras(devices) {
    cameraList.classList.remove('hidden');
    devices.forEach((dev) => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'camera-chip';
      chip.innerHTML = `<span class="camera-name">${dev.name || t('camera')}</span><span class="camera-addr">${dev.host}:${dev.port}</span>`;
      chip.addEventListener('click', () => {
        cameraList.querySelectorAll('.camera-chip').forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');
        selectedCamera = dev;
        selectedProfile = null;
        profileList.classList.add('hidden');
        profileList.innerHTML = '';
        btnCameraConnect.disabled = true;
        cameraCreds.classList.remove('hidden');
        inputCameraUser.focus();
      });
      cameraList.appendChild(chip);
    });
  }

  function renderProfiles(profiles) {
    profileList.innerHTML = '';
    profileList.classList.remove('hidden');
    profiles.forEach((p) => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'profile-chip';
      chip.textContent = p.name;
      chip.addEventListener('click', () => {
        profileList.querySelectorAll('.profile-chip').forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');
        selectedProfile = p;
        btnCameraConnect.disabled = false;
      });
      profileList.appendChild(chip);
    });
    const first = profileList.querySelector('.profile-chip');
    if (first) {
      first.classList.add('active');
      selectedProfile = profiles[0];
      btnCameraConnect.disabled = false;
    }
  }

  // ---- Boot ----
  async function loadSources() {
    try {
      const resp = await fetch('/api/sources');
      if (!resp.ok) return;
      const data = await resp.json();
      (data.sources || []).forEach((src) => createTile(src));
    } catch (err) {
      console.error('Failed to load sources:', err);
    }
  }

  function init() {
    setupTheme();
    setupLang();
    setupFocusEvents();
    setupFeedEvents();
    loadSources();
    reloadVideoList();
    loadReports();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();