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

  const connectionBadge = document.getElementById('connection-badge');
  const connectionText = document.getElementById('connection-text');
  const latencyVal = document.getElementById('latency-val');
  const fpsVal = document.getElementById('fps-val');

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
  const selectDirection = document.getElementById('select-direction');
  const btnApplyDir = document.getElementById('btn-apply-dir');

  const selectVideoSource = document.getElementById('select-video-source');
  const btnSwitchSource = document.getElementById('btn-switch-source');
  const btnTriggerUpload = document.getElementById('btn-trigger-upload');
  const inputVideoFile = document.getElementById('input-video-file');
  const uploadProgressMsg = document.getElementById('upload-progress-msg');

  const cfgSource = document.getElementById('cfg-source');
  const cfgRes = document.getElementById('cfg-res');
  const cfgLine = document.getElementById('cfg-line');
  const cfgOrient = document.getElementById('cfg-orient');
  const cfgDir = document.getElementById('cfg-dir');

  // State
  let wsVideo = null;
  let wsCounts = null;
  let isVideoConnected = false;
  let isCountsConnected = false;

  let currentLine = null;
  let currentRes = [0, 0];

  // FPS & Latency tracking
  let frameCount = 0;
  let lastFpsCalc = performance.now();
  let latencyRolling = 0;

  // Drawing state
  let isDrawing = false;
  let drawPoint1 = null;
  let drawPoint2 = null;
  let currentHoverPos = null;

  // Last crossing timer
  let lastCrossingTimer = null;

  function init() {
    setupWebSockets();
    setupDrawingEvents();
    setupButtonEvents();
  }

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

  function updateConnectionStatus() {
    const connected = isVideoConnected && isCountsConnected;
    if (connected) {
      connectionBadge.className = 'connection-status status-connected';
      connectionText.textContent = 'Live Synced';
    } else {
      connectionBadge.className = 'connection-status status-disconnected';
      connectionText.textContent = isVideoConnected ? 'Telemetry Reconnecting' : 'Connecting';
    }
  }

  function connectVideoWs() {
    const url = getWsUrl('/ws/video');
    wsVideo = new WebSocket(url);
    wsVideo.binaryType = 'arraybuffer';

    wsVideo.onopen = () => {
      isVideoConnected = true;
      updateConnectionStatus();
    };

    wsVideo.onmessage = async (event) => {
      try {
        const buffer = event.data;
        if (buffer.byteLength < 8) return;

        // Extract 8-byte big-endian server timestamp
        const view = new DataView(buffer);
        const serverTs = Number(view.getBigInt64(0));
        const now = Date.now();
        const latency = Math.max(0, now - serverTs);

        // Exponential moving average for latency
        latencyRolling = latencyRolling === 0 ? latency : Math.round(latencyRolling * 0.8 + latency * 0.2);
        latencyVal.textContent = `${latencyRolling} ms`;

        // Measure FPS
        frameCount++;
        const nowPerf = performance.now();
        if (nowPerf - lastFpsCalc >= 1000) {
          const fps = ((frameCount * 1000) / (nowPerf - lastFpsCalc)).toFixed(1);
          fpsVal.textContent = fps;
          frameCount = 0;
          lastFpsCalc = nowPerf;
        }

        // Decode JPEG with createImageBitmap for fastest hardware-accelerated decode
        const jpegBlob = new Blob([buffer.slice(8)], { type: 'image/jpeg' });
        const bitmap = await createImageBitmap(jpegBlob);

        // Resize canvas buffers to match incoming frame native dimensions
        if (videoCanvas.width !== bitmap.width || videoCanvas.height !== bitmap.height) {
          videoCanvas.width = bitmap.width;
          videoCanvas.height = bitmap.height;
          overlayCanvas.width = bitmap.width;
          overlayCanvas.height = bitmap.height;
          currentRes = [bitmap.width, bitmap.height];
          cfgRes.textContent = `${bitmap.width} × ${bitmap.height}`;
        }

        videoCtx.drawImage(bitmap, 0, 0);
        bitmap.close();
      } catch (err) {
        console.error('Frame decode error:', err);
      }
    };

    wsVideo.onclose = () => {
      isVideoConnected = false;
      updateConnectionStatus();
      setTimeout(connectVideoWs, 1500);
    };

    wsVideo.onerror = () => {
      wsVideo.close();
    };
  }

  function connectCountsWs() {
    const url = getWsUrl('/ws/counts');
    wsCounts = new WebSocket(url);

    wsCounts.onopen = () => {
      isCountsConnected = true;
      updateConnectionStatus();
    };

    wsCounts.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Update counts
        statInVal.textContent = data.in ?? 0;
        statOutVal.textContent = data.out ?? 0;
        statCurrentVal.textContent = data.current ?? 0;

        // Last crossing notification
        if (data.last_crossing && data.last_crossing.trim() !== '') {
          const formatted = data.last_crossing.replace('_to_', ' → ').toUpperCase();
          lastCrossingText.textContent = `LAST: ${formatted}`;
          lastCrossingTag.classList.remove('hidden');

          if (lastCrossingTimer) clearTimeout(lastCrossingTimer);
          lastCrossingTimer = setTimeout(() => {
            lastCrossingTag.classList.add('hidden');
          }, 3000);
        }

        // Active config display
        if (data.line) {
          currentLine = data.line;
          cfgLine.textContent = `${data.line[0]}, ${data.line[1]} → ${data.line[2]}, ${data.line[3]}`;
          const isHoriz = Math.abs(data.line[2] - data.line[0]) >= Math.abs(data.line[3] - data.line[1]);
          cfgOrient.textContent = isHoriz ? 'Horizontal' : 'Vertical';
        }
        if (data.entering_direction) {
          cfgDir.textContent = data.entering_direction.replace(/_/g, ' ');
        }
        if (data.resolution && data.resolution[0] > 0) {
          cfgRes.textContent = `${data.resolution[0]} × ${data.resolution[1]}`;
        }
      } catch (err) {
        console.error('Counts parse error:', err);
      }
    };

    wsCounts.onclose = () => {
      isCountsConnected = false;
      updateConnectionStatus();
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
    drawPrompt.textContent = 'Click point 1 on the video to start the line';
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
      drawPrompt.textContent = 'Click point 1 on the video to start the line';
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
      drawPrompt.textContent = `Point 1 set (${coords.x}, ${coords.y}). Click point 2 to complete line.`;
      renderOverlay();
    } else if (!drawPoint2) {
      drawPoint2 = coords;
      btnDrawConfirm.disabled = false;
      drawPrompt.textContent = `Line ready: (${drawPoint1.x}, ${drawPoint1.y}) → (${drawPoint2.x}, ${drawPoint2.y}). Click Confirm.`;
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
      btnDrawConfirm.textContent = 'Saving...';

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
      alert(`Failed to save line: ${err.message}`);
    } finally {
      btnDrawConfirm.textContent = 'Confirm Line';
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

    btnApplyDir.addEventListener('click', async () => {
      const selected = selectDirection.value || null;
      if (!currentLine) {
        alert('No counting line configured yet.');
        return;
      }

      try {
        btnApplyDir.textContent = 'Applying...';
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
      } catch (err) {
        alert(`Failed to update direction: ${err.message}`);
      } finally {
        btnApplyDir.textContent = 'Update Logic';
      }
    });

    btnSwitchSource.addEventListener('click', async () => {
      const selected = selectVideoSource.value;
      if (!selected) return;
      try {
        btnSwitchSource.textContent = 'Switching...';
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
        alert(`Failed to switch video: ${err.message}`);
      } finally {
        btnSwitchSource.textContent = 'Switch Feed';
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
        uploadProgressMsg.textContent = `Uploading ${file.name}...`;
        btnTriggerUpload.disabled = true;

        const resp = await fetch('/api/upload', {
          method: 'POST',
          body: formData,
        });

        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const result = await resp.json();

        uploadProgressMsg.textContent = `Active: ${result.filename}`;
        setTimeout(() => {
          uploadProgressMsg.classList.add('hidden');
        }, 3000);

        await loadAvailableVideos(result.source);
        cfgSource.textContent = result.filename;
      } catch (err) {
        alert(`Upload failed: ${err.message}`);
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

  function init() {
    setupWebSockets();
    setupDrawingEvents();
    setupButtonEvents();
    loadAvailableVideos();
  }

  // Initialize once DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

