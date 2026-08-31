/**
 * VisionCounter Frontend Application
 * High-performance WebSocket MJPEG stream rendering & interactive line drawing
 */

(function () {
  'use strict';

  // Elements
  const videoCanvas = document.getElementById('video-canvas');
  const overlayCanvas = document.getElementById('overlay-canvas');
  const videoWrapper = document.getElementById('video-wrapper');
  const videoCtx = videoCanvas.getContext('2d');
  const overlayCtx = overlayCanvas.getContext('2d');

  const statInVal = document.getElementById('stat-in-val');
  const statOutVal = document.getElementById('stat-out-val');
  const statCurrentVal = document.getElementById('stat-current-val');

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

  const selectVideoSource = document.getElementById('select-video-source');
  const btnSwitchSource = document.getElementById('btn-switch-source');
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

  const modelChips = document.getElementById('model-chips');
  const cfgModel = document.getElementById('cfg-model');

  const hwCpuName = document.getElementById('hw-cpu-name');
  const hwGpuList = document.getElementById('hw-gpu-list');
  const hwNoGpu = document.getElementById('hw-no-gpu');
  const hwDevices = document.getElementById('hw-devices');
  const hardwareStatus = document.getElementById('hardware-status');
  const hwSpeed = document.getElementById('hw-speed');
  const cfgDevice = document.getElementById('cfg-device');

  let selectedCamera = null;
  let selectedProfile = null;
  let cameraStatusTimer = null;

  function setCameraStatus(msg, transient) {
    if (!cameraStatus) return;
    cameraStatus.textContent = msg;
    cameraStatus.classList.remove('hidden');
    clearTimeout(cameraStatusTimer);
    if (transient) {
      cameraStatusTimer = setTimeout(() => cameraStatus.classList.add('hidden'), 3500);
    }
  }

  const cfgSource = document.getElementById('cfg-source');
  const cfgLine = document.getElementById('cfg-line');
  const deviceBadge = document.getElementById('device-badge');

  function set(el, value) {
    if (el) el.textContent = value;
  }

  const I18N = {
    en: {
      title: 'People Counter — Live visitor counting',
      brandSub: 'Live visitor counts for your space',
      source: 'Source:',
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
      switch: 'Load',
      uploadVideo: 'Upload video',
      uploading: 'Uploading video…',
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
      switching: 'Switching…',
      failedSwitch: 'Failed to switch video: {0}',
      uploadingFile: 'Uploading {0}...',
      nowPlaying: 'Now playing: {0}',
      uploadFailed: 'Upload failed: {0}',
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
      detectionModel: 'Detection model',
      modelHint: 'Larger models are more accurate but slower.',
      modelChanged: 'Model changed to {0}',
      modelFailed: 'Could not switch model: {0}',
      downloading: 'Loading…',
      hardware: 'Hardware',
      cpu: 'CPU',
      gpu: 'GPU',
      noGpuDetected: 'No GPU detected — using CPU',
      vram: 'VRAM',
      cudaVersion: 'CUDA',
      switchDevice: 'Switch',
      deviceChanged: 'Switched to {0}',
      deviceFailed: 'Could not switch: {0}',
      scanningHardware: 'Scanning…',
      currentDevice: 'Current',
      speed: 'Speed',
      fpsUnit: 'frames/s',
      gpuError: 'GPU found but unusable: {0}',
    },
    fr: {
      title: 'Compteur de personnes — Comptage de visiteurs en direct',
      brandSub: 'Comptage en direct des visiteurs de votre espace',
      source: 'Source :',
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
      switch: 'Charger',
      uploadVideo: 'Importer une vidéo',
      uploading: 'Import de la vidéo…',
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
      switching: 'Changement…',
      failedSwitch: 'Échec du changement de vidéo : {0}',
      uploadingFile: 'Import de {0}...',
      nowPlaying: 'Lecture : {0}',
      uploadFailed: 'Échec de l’import : {0}',
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
      detectionModel: 'Modèle de détection',
      modelHint: 'Les modèles plus grands sont plus précis mais plus lents.',
      modelChanged: 'Modèle changé pour {0}',
      modelFailed: 'Impossible de changer le modèle : {0}',
      downloading: 'Chargement…',
      hardware: 'Matériel',
      cpu: 'Processeur',
      gpu: 'Carte graphique',
      noGpuDetected: 'Aucune carte graphique détectée — utilisation du processeur',
      vram: 'Mémoire vidéo',
      cudaVersion: 'CUDA',
      switchDevice: 'Changer',
      deviceChanged: 'Périphérique changé pour {0}',
      deviceFailed: 'Impossible de changer : {0}',
      scanningHardware: 'Analyse…',
      currentDevice: 'Actuel',
      speed: 'Vitesse',
      fpsUnit: 'images/s',
      gpuError: 'Carte graphique détectée mais inutilisable : {0}',
    },
  };

  let currentLang = 'en';

  function t(key, ...params) {
    const str = (I18N[currentLang] && I18N[currentLang][key]) || I18N.en[key] || key;
    return params.reduce((acc, p, i) => acc.replace(`{${i}}`, p), str);
  }

  function applyLang() {
    document.documentElement.lang = currentLang;
    const toggle = document.getElementById('lang-toggle');
    if (toggle) toggle.textContent = currentLang === 'en' ? 'FR' : 'EN';
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      set(el, t(el.dataset.i18n));
    });
    document.title = t('title');
    if (cfgLine) cfgLine.textContent = currentLine ? t('lineIsSet') : t('noLineYet');
    if (isDrawing) {
      set(drawPrompt, !drawPoint1 ? t('step1') : (!drawPoint2 ? t('step2') : t('lineLooksGood')));
    }
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

  const dirHint = document.getElementById('dir-hint');
  let dirHintTimer = null;

  function showDirHint(msg) {
    if (!dirHint) return;
    dirHint.textContent = msg;
    dirHint.classList.remove('hidden');
    clearTimeout(dirHintTimer);
    dirHintTimer = setTimeout(() => dirHint.classList.add('hidden'), 2500);
  }

  function setActiveDir(value) {
    document.querySelectorAll('.dir-btn').forEach((btn) => {
      btn.classList.toggle('active', (btn.dataset.value || null) === (value || null));
    });
  }

  // State
  let wsVideo = null;
  let wsCounts = null;

  let currentLine = null;

  // Drawing state
  let isDrawing = false;
  let drawPoint1 = null;
  let drawPoint2 = null;
  let currentHoverPos = null;

  // Last crossing timer
  let lastCrossingTimer = null;

  // --- WebSocket Connection ---
  function getWsUrl(endpoint) {
    const loc = window.location;
    const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = loc.host || 'localhost:8000';
    return `${proto}//${host}${endpoint}`;
  }

  function setupWebSockets() {
    connectVideoWs();
    connectCountsWs();
  }

  function reloadStream() {
    if (wsVideo) {
      wsVideo.onclose = null;
      wsVideo.close();
    }
    if (wsCounts) {
      wsCounts.onclose = null;
      wsCounts.close();
    }
    connectVideoWs();
    connectCountsWs();
  }

  function connectVideoWs() {
    const url = getWsUrl('/ws/video');
    wsVideo = new WebSocket(url);
    wsVideo.binaryType = 'arraybuffer';

    wsVideo.onmessage = async (event) => {
      try {
        const buffer = event.data;
        if (buffer.byteLength < 8) return;

        // Decode JPEG with createImageBitmap for fastest hardware-accelerated decode
        const jpegBlob = new Blob([buffer.slice(8)], { type: 'image/jpeg' });
        const bitmap = await createImageBitmap(jpegBlob);

        // Resize canvas buffers to match incoming frame native dimensions
        if (videoCanvas.width !== bitmap.width || videoCanvas.height !== bitmap.height) {
          videoCanvas.width = bitmap.width;
          videoCanvas.height = bitmap.height;
          overlayCanvas.width = bitmap.width;
          overlayCanvas.height = bitmap.height;
        }

        videoCtx.drawImage(bitmap, 0, 0);
        bitmap.close();
      } catch (err) {
        console.error('Frame decode error:', err);
      }
    };

    wsVideo.onclose = () => {
      setTimeout(connectVideoWs, 1500);
    };

    wsVideo.onerror = () => {
      wsVideo.close();
    };
  }

  function connectCountsWs() {
    const url = getWsUrl('/ws/counts');
    wsCounts = new WebSocket(url);

    wsCounts.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Update counts
        statInVal.textContent = data.in ?? 0;
        statOutVal.textContent = data.out ?? 0;
        statCurrentVal.textContent = data.current ?? 0;

        // Live processing speed — proves model/device switches took effect
        if (hwSpeed) {
          hwSpeed.textContent = data.fps > 0 ? `${Math.round(data.fps)} ${t('fpsUnit')}` : '—';
        }

        // Last crossing notification
        if (data.last_crossing && data.last_crossing.trim() !== '') {
          set(lastCrossingText, t('visitorCounted'));
          lastCrossingTag.classList.remove('hidden');

          if (lastCrossingTimer) clearTimeout(lastCrossingTimer);
          lastCrossingTimer = setTimeout(() => {
            lastCrossingTag.classList.add('hidden');
          }, 3000);
        }

        // Active config display
        if (data.line) {
          currentLine = data.line;
          if (cfgLine) {
            cfgLine.textContent = t('lineIsSet');
            cfgLine.classList.add('ok');
          }
        }
        if (data.entering_direction) {
          setActiveDir(data.entering_direction);
        }
      } catch (err) {
        console.error('Counts parse error:', err);
      }
    };

    wsCounts.onclose = () => {
      setTimeout(connectCountsWs, 1500);
    };

    wsCounts.onerror = () => {
      wsCounts.close();
    };
  }

  // --- Interactive Line Drawing ---
  function setupDrawingEvents() {
    btnDrawToggle.addEventListener('click', () => {
      if (isDrawing) {
        stopDrawingMode();
      } else {
        startDrawingMode();
      }
    });

    btnDrawReset.addEventListener('click', resetDrawingPoints);
    btnDrawCancel.addEventListener('click', stopDrawingMode);
    btnDrawConfirm.addEventListener('click', confirmLine);

    overlayCanvas.addEventListener('click', handleCanvasClick);
    overlayCanvas.addEventListener('mousemove', handleCanvasMouseMove);
  }

  function startDrawingMode() {
    isDrawing = true;
    resetDrawingPoints();
    videoWrapper.classList.add('drawing-active');
    drawActions.classList.remove('hidden');
    drawBanner.classList.remove('hidden');
    btnDrawToggle.classList.add('hidden');
    drawPrompt.textContent = t('step1');
  }

  function stopDrawingMode() {
    isDrawing = false;
    resetDrawingPoints();
    videoWrapper.classList.remove('drawing-active');
    drawActions.classList.add('hidden');
    drawBanner.classList.add('hidden');
    btnDrawToggle.classList.remove('hidden');
    clearOverlay();
  }

  function resetDrawingPoints() {
    drawPoint1 = null;
    drawPoint2 = null;
    currentHoverPos = null;
    btnDrawConfirm.disabled = true;
    if (isDrawing) {
      drawPrompt.textContent = t('step1');
    }
    clearOverlay();
  }

  function getCanvasCoords(e) {
    const rect = overlayCanvas.getBoundingClientRect();
    const scaleX = overlayCanvas.width / rect.width;
    const scaleY = overlayCanvas.height / rect.height;
    return {
      x: Math.round((e.clientX - rect.left) * scaleX),
      y: Math.round((e.clientY - rect.top) * scaleY),
    };
  }

  function handleCanvasClick(e) {
    if (!isDrawing) return;

    const coords = getCanvasCoords(e);

    if (!drawPoint1) {
      drawPoint1 = coords;
      drawPrompt.textContent = t('step2');
      renderOverlay();
    } else if (!drawPoint2) {
      drawPoint2 = coords;
      btnDrawConfirm.disabled = false;
      drawPrompt.textContent = t('lineLooksGood');
      renderOverlay();
    }
  }

  function handleCanvasMouseMove(e) {
    if (!isDrawing) return;
    currentHoverPos = getCanvasCoords(e);
    renderOverlay();
  }

  function clearOverlay() {
    overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
  }

  function renderOverlay() {
    clearOverlay();
    if (!isDrawing) return;

    // Draw point 1 marker
    if (drawPoint1) {
      drawMarker(drawPoint1.x, drawPoint1.y, '#10b981', 'P1');

      // Draw line to point 2 or to current hover
      const endPoint = drawPoint2 || currentHoverPos;
      if (endPoint) {
        overlayCtx.beginPath();
        overlayCtx.strokeStyle = '#d97706';
        overlayCtx.lineWidth = 2.5;
        overlayCtx.setLineDash(drawPoint2 ? [] : [6, 4]);
        overlayCtx.moveTo(drawPoint1.x, drawPoint1.y);
        overlayCtx.lineTo(endPoint.x, endPoint.y);
        overlayCtx.stroke();
        overlayCtx.setLineDash([]);
      }
    }

    // Draw point 2 marker
    if (drawPoint2) {
      drawMarker(drawPoint2.x, drawPoint2.y, '#d97706', 'P2');
    }
  }

  function drawMarker(x, y, color, label) {
    overlayCtx.beginPath();
    overlayCtx.arc(x, y, 7, 0, Math.PI * 2);
    overlayCtx.fillStyle = color;
    overlayCtx.fill();
    overlayCtx.strokeStyle = '#ffffff';
    overlayCtx.lineWidth = 2;
    overlayCtx.stroke();

    overlayCtx.font = 'bold 12px JetBrains Mono, sans-serif';
    overlayCtx.fillStyle = '#ffffff';
    overlayCtx.fillText(`${label} (${x}, ${y})`, x + 12, y - 8);
  }

  async function confirmLine() {
    if (!drawPoint1 || !drawPoint2) return;

    try {
      btnDrawConfirm.disabled = true;
      btnDrawConfirm.textContent = t('saving');

      const payload = {
        x1: drawPoint1.x,
        y1: drawPoint1.y,
        x2: drawPoint2.x,
        y2: drawPoint2.y,
      };

      const resp = await fetch('/api/line', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const result = await resp.json();
      currentLine = result.line;

      stopDrawingMode();
    } catch (err) {
      alert(t('failedSaveLine', err.message));
    } finally {
      btnDrawConfirm.textContent = t('saveLine');
      btnDrawConfirm.disabled = false;
    }
  }

  // --- Button & Form Events ---
  function setupButtonEvents() {
    btnResetCounts.addEventListener('click', async () => {
      try {
        await fetch('/api/reset', { method: 'POST' });
      } catch (err) {
        console.error('Failed to reset counts:', err);
      }
    });

    document.querySelectorAll('.dir-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const selected = btn.dataset.value || null;
        if (!currentLine) {
          showDirHint(t('setLineFirst'));
          return;
        }

        try {
          await fetch('/api/line', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              x1: currentLine[0],
              y1: currentLine[1],
              x2: currentLine[2],
              y2: currentLine[3],
              entering_direction: selected,
            }),
          });
          setActiveDir(selected);
          showDirHint(t('saved'));
        } catch (err) {
          showDirHint(t('couldNotSave'));
        }
      });
    });

    btnSwitchSource.addEventListener('click', async () => {
      const selected = selectVideoSource.value;
      if (!selected) return;
      try {
        btnSwitchSource.textContent = t('switching');
        const resp = await fetch('/api/source', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source: selected }),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        const baseName = data.source.split(/[\\/]/).pop();
        cfgSource.textContent = baseName;
      } catch (err) {
        alert(t('failedSwitch', err.message));
      } finally {
        btnSwitchSource.textContent = t('switch');
      }
    });

    btnTriggerUpload.addEventListener('click', () => {
      inputVideoFile.click();
    });

    inputVideoFile.addEventListener('change', async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;

      const formData = new FormData();
      formData.append('file', file);

      try {
        uploadProgressMsg.classList.remove('hidden');
        uploadProgressMsg.textContent = t('uploadingFile', file.name);
        btnTriggerUpload.disabled = true;

        const resp = await fetch('/api/upload', {
          method: 'POST',
          body: formData,
        });

        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const result = await resp.json();

        uploadProgressMsg.textContent = t('nowPlaying', result.filename);
        setTimeout(() => {
          uploadProgressMsg.classList.add('hidden');
        }, 3000);

        await loadAvailableVideos(result.source);
        cfgSource.textContent = result.filename;
      } catch (err) {
        alert(t('uploadFailed', err.message));
        uploadProgressMsg.classList.add('hidden');
      } finally {
        btnTriggerUpload.disabled = false;
        inputVideoFile.value = '';
      }
    });
  }

  async function loadAvailableVideos(preferredSelected = null) {
    try {
      const resp = await fetch('/api/videos');
      if (!resp.ok) return;
      const data = await resp.json();
      const videos = data.videos || [];

      selectVideoSource.innerHTML = '';
      videos.forEach((vid) => {
        const opt = document.createElement('option');
        opt.value = vid;
        opt.textContent = vid.split(/[\\/]/).pop();
        if (preferredSelected && vid === preferredSelected) {
          opt.selected = true;
        }
        selectVideoSource.appendChild(opt);
      });
    } catch (err) {
      console.error('Failed to load video list:', err);
    }
  }

  async function loadModels() {
    try {
      const resp = await fetch('/api/models');
      if (!resp.ok) return;
      const data = await resp.json();
      const models = data.models || [];
      if (cfgModel) cfgModel.textContent = data.current || '';

      modelChips.innerHTML = '';
      models.forEach((m) => {
        if (!m.downloaded && !m.active) return; // not installed on this PC — don't offer it
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'seg-btn' + (m.active ? ' active' : '');
        chip.dataset.model = m.file;
        chip.textContent = m.name + ' — ' + m.label;
        chip.addEventListener('click', () => switchModel(m.file, chip));
        modelChips.appendChild(chip);
      });
    } catch (err) {
      console.error('Failed to load models:', err);
    }
  }

  async function switchModel(file, chip) {
    if (chip.classList.contains('active')) return;
    const prev = chip.textContent;
    chip.textContent = t('downloading');
    chip.disabled = true;
    try {
      const resp = await fetch('/api/model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: file }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => null);
        throw new Error(data?.detail || `HTTP ${resp.status}`);
      }
      await loadModels(); // rebuild chips from server truth (active flag)
      loadConfig();
    } catch (err) {
      alert(t('modelFailed', err.message));
      chip.textContent = prev;
    } finally {
      chip.disabled = false;
    }
  }

  async function scanHardware() {
    if (hardwareStatus) {
      hardwareStatus.textContent = t('scanningHardware');
      hardwareStatus.classList.remove('hidden');
    }
    try {
      const resp = await fetch('/api/hardware');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      renderHardwareInfo(data);
    } catch (err) {
      if (hardwareStatus) hardwareStatus.textContent = t('couldNotScan', err.message);
    }
  }

  function renderHardwareInfo(data) {
    if (hardwareStatus) hardwareStatus.classList.add('hidden');
    if (hwCpuName) hwCpuName.textContent = data.cpu || '—';

    if (hwGpuList) hwGpuList.innerHTML = '';
    if (hwNoGpu) {
      if (data.gpus.length === 0) {
        hwNoGpu.textContent = data.cuda_error ? t('gpuError', data.cuda_error) : t('noGpuDetected');
        hwNoGpu.classList.remove('hidden');
      } else {
        hwNoGpu.classList.add('hidden');
      }
    }

    data.gpus.forEach((gpu) => {
      const card = document.createElement('div');
      card.className = 'hw-gpu-card';
      const vram = gpu.vram_free_gb !== undefined
        ? `${(gpu.vram_gb - gpu.vram_free_gb).toFixed(1)} / ${gpu.vram_gb} GB`
        : `${gpu.vram_gb} GB`;
      card.innerHTML = `<span class="hw-gpu-name">${gpu.name}</span><span class="hw-gpu-detail">${t('vram')}: ${vram}</span>`;
      hwGpuList.appendChild(card);
    });

    if (data.cuda_version && hwGpuList && data.gpus.length > 0) {
      const cudaRow = document.createElement('div');
      cudaRow.className = 'hw-row';
      cudaRow.innerHTML = `<span class="hw-label">${t('cudaVersion')}</span><span class="hw-value">${data.cuda_version}</span>`;
      hwGpuList.appendChild(cudaRow);
    }

    renderDeviceChips(data);
  }

  function renderDeviceChips(data) {
    if (!hwDevices) return;
    hwDevices.innerHTML = '';
    const current = data.current_device || 'cpu';

    if (data.gpus.length > 0) {
      data.gpus.forEach((gpu) => {
        const dev = `cuda:${gpu.index}`;
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'hw-device-chip' + (current === dev ? ' active' : '');
        chip.textContent = gpu.name.replace('NVIDIA ', '');
        chip.addEventListener('click', () => switchDevice(dev, chip));
        hwDevices.appendChild(chip);
      });
    }

    const cpuChip = document.createElement('button');
    cpuChip.type = 'button';
    cpuChip.className = 'hw-device-chip' + (current === 'cpu' ? ' active' : '');
    cpuChip.textContent = 'CPU';
    cpuChip.addEventListener('click', () => switchDevice('cpu', cpuChip));
    hwDevices.appendChild(cpuChip);
  }

  async function switchDevice(device, chip) {
    if (chip.classList.contains('active')) return;
    const prev = chip.textContent;
    chip.textContent = t('switchDevice');
    chip.disabled = true;
    try {
      const resp = await fetch('/api/device', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => null);
        throw new Error(data?.detail || `HTTP ${resp.status}`);
      }
      await scanHardware(); // rebuild chips from server truth (current device)
      loadConfig();
    } catch (err) {
      alert(t('deviceFailed', err.message));
      chip.textContent = prev;
    } finally {
      chip.disabled = false;
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
        set(cfgSource, data.host);
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

  async function loadConfig() {
    try {
      const resp = await fetch('/api/config');
      if (!resp.ok) return;
      const data = await resp.json();
      if (deviceBadge) {
        const dev = (data.device || 'cpu').toUpperCase();
        const model = data.model || '';
        deviceBadge.textContent = dev + (model ? ' · ' + model : '');
      }
      if (cfgDevice) cfgDevice.textContent = (data.device || 'cpu').toUpperCase();
      if (data.source) {
        const base = data.source.split(/[\\/]/).pop();
        if (cfgSource) cfgSource.textContent = base;
      }
    } catch (err) {
      console.error('Failed to load config:', err);
    }
  }

  function init() {
    setupTheme();
    setupLang();
    setupWebSockets();
    setupDrawingEvents();
    setupButtonEvents();
    setupFeedEvents();
    loadModels();
    loadAvailableVideos();
    loadConfig();
    scanHardware();
  }

  // Initialize once DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

