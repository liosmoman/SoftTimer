#!/usr/bin/env python3
"""
Neumorphic Countdown Timer — HTML-based, compact webview window.
Click the time to type a duration (25, 1:30, 90s, 1h30m) or scroll to set.
Selectable alert sounds. RGB flash on time-up.
"""

import webview
import wave
import struct
import math
import os
import tempfile


# ── Sound generator (pure Python, no external deps) ─────
def _gen_wav(filename, freq_fn, duration=1.5, sample_rate=44100, volume=0.7):
    """Generate a WAV file from a frequency-function over time."""
    n_samples = int(sample_rate * duration)
    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        freq = freq_fn(t)
        v = math.sin(2 * math.pi * freq * t) * volume * (1 - t/duration * 0.3)
        samples.append(v)
    max_val = max(abs(s) for s in samples) or 1
    scale = min(32767 / max_val, 1)
    with wave.open(filename, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for s in samples:
            wf.writeframes(struct.pack("<h", int(s * scale * 32767)))


def _build_sound_dir():
    d = os.path.join(tempfile.gettempdir(), "softtimer_sounds")
    os.makedirs(d, exist_ok=True)
    files = {}
    # ── Beep: classic repeating beep ──
    bp = os.path.join(d, "beep.wav")
    if not os.path.exists(bp):
        _gen_wav(bp, lambda t: 880 if (t % 0.4) < 0.15 else 0, duration=2.0)
    files["beep"] = bp

    # ── Chime: 3-note ascending chime ──
    ch = os.path.join(d, "chime.wav")
    if not os.path.exists(ch):
        def chime_fn(t):
            if t < 0.5:   return 523   # C5
            if t < 1.0:   return 659   # E5
            if t < 1.5:   return 784   # G5
            return 0
        _gen_wav(ch, chime_fn, duration=2.0)
    files["chime"] = ch

    # ── Gentle: soft two-tone ──
    gn = os.path.join(d, "gentle.wav")
    if not os.path.exists(gn):
        def gentle_fn(t):
            if t < 0.8: return 440
            return 554 if t < 1.5 else 0
        _gen_wav(gn, gentle_fn, duration=2.0, volume=0.5)
    files["gentle"] = gn

    # ── Urgent: fast alarm ──
    ug = os.path.join(d, "urgent.wav")
    if not os.path.exists(ug):
        _gen_wav(ug, lambda t: 1000 if t % 0.3 < 0.2 else 600, duration=2.5)
    files["urgent"] = ug

    return files


SOUND_PATHS = _build_sound_dir()


class TimerAPI:
    """Python backend for timer window."""

    def __init__(self):
        self._window = None
        self._sound_choice = "chime"  # default

    def set_window(self, w):
        self._window = w

    def close_window(self):
        if self._window:
            self._window.destroy()

    def get_sound_choices(self):
        """Return available sound names."""
        return list(SOUND_PATHS.keys())

    def set_sound(self, name):
        """Set the alert sound."""
        if name in SOUND_PATHS:
            self._sound_choice = name

    def play_alert(self):
        """Play the selected alert sound using winsound."""
        import winsound
        path = SOUND_PATHS.get(self._sound_choice, SOUND_PATHS["chime"])
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)


HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  :root {
    --bg: #e2e4e6;
    --text: #5d6770;
    --shadow-d: rgba(165,170,174,0.5);
    --shadow-l: rgba(255,255,255,0.8);
    --accent: #ff5500;
  }
  * { box-sizing:border-box; margin:0; padding:0; }
  body {
    background: var(--bg);
    font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
    color: var(--text);
    user-select: none;
    -webkit-user-select: none;
  }
  .container {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
  }
  .ring {
    position: relative;
    width: 100px;
    height: 100px;
    display: flex;
    justify-content: center;
    align-items: center;
    border-radius: 50%;
    background: var(--bg);
    box-shadow: 5px 5px 10px var(--shadow-d),
               -5px -5px 10px var(--shadow-l);
    cursor: pointer;
    transition: box-shadow 0.15s;
  }
  .ring svg { transform: rotate(-90deg); width: 100%; height: 100%; }
  .ring-bg    { fill:none; stroke:#d0d3d6; stroke-width:5; }
  .ring-fill  {
    fill:none; stroke:var(--accent); stroke-width:5;
    stroke-linecap:round; transition: stroke-dashoffset 1s linear;
  }
  /* flashing ring states — background changes via JS class toggles */
  .ring.flash-red  .ring-fill { stroke:#ff2222; }
  .ring.flash-blue .ring-fill { stroke:#4488ff; }
  .ring.flash-green .ring-fill { stroke:#22dd44; }
  .time-display {
    position: absolute;
    font-size: 1.15rem;
    font-weight: 600;
    letter-spacing: 0.5px;
    color: var(--text);
    cursor: pointer;
  }
  /* manual-entry field — sized to sit clear of the orange progress stroke.
     Ring is 100px; stroke inner edge is at r=41.5px, so the field's corner
     radius (w/2, h/2) must stay inside that (~40.5px keeps a small gap). */
  .time-edit {
    position: absolute;
    inset: 0;
    margin: auto;
    width: 78px;
    height: 22px;
    font-family: inherit;
    font-size: 1rem;
    font-weight: 600;
    letter-spacing: 0.3px;
    text-align: center;
    color: var(--text);
    background: transparent;
    border: none;
    outline: none;
    padding: 0 5px;
    border-radius: 7px;
    box-shadow: inset 1.5px 1.5px 4px var(--shadow-d),
                inset -1.5px -1.5px 4px var(--shadow-l);
    user-select: text;
    -webkit-user-select: text;
  }
  .hint { font-size: 0.5rem; color: #999; margin-top: -2px; }
  .btn {
    border: none; outline: none;
    background: var(--bg);
    color: var(--text);
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
    box-shadow: 3px 3px 8px var(--shadow-d),
               -3px -3px 8px var(--shadow-l);
    font-family: inherit;
  }
  .btn:active {
    box-shadow: inset 2px 2px 4px var(--shadow-d),
                inset -2px -2px 4px var(--shadow-l);
    transform: scale(0.97);
  }
  .btn-play    { padding: 5px 14px; font-size: 0.65rem; border-radius: 8px; }
  .btn-reset   { padding: 5px 14px; font-size: 0.65rem; border-radius: 8px; }
  .btn-close   { padding:  3px 10px; font-size: 0.6rem; border-radius: 6px; }
  .row { display: flex; gap: 8px; }
  /* interval counter */
  .count-pill {
    display: flex;
    align-items: center;
    gap: 5px;
    background: var(--bg);
    padding: 2px 11px;
    border-radius: 8px;
    box-shadow: inset 2px 2px 4px var(--shadow-d),
                inset -2px -2px 4px var(--shadow-l);
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--text);
    min-width: 56px;
    justify-content: center;
  }
  .count-label {
    font-size: 0.45rem;
    font-weight: 500;
    color: #999;
    letter-spacing: 0.4px;
    text-transform: uppercase;
  }
  .btn-count-reset { padding: 2px 9px; font-size: 0.6rem; border-radius: 7px; }
  .perhour {
    font-size: 1.04rem;   /* twice the previous 0.52rem */
    color: #7a8087;
    margin-top: 0;
    white-space: nowrap;
  }
  /* Sound selector */
  .sound-select {
    background: var(--bg);
    color: var(--text);
    border: none; outline: none;
    font-size: 0.55rem;
    font-family: inherit;
    box-shadow: inset 2px 2px 4px var(--shadow-d),
                inset -2px -2px 4px var(--shadow-l);
    border-radius: 6px;
    padding: 3px 8px;
    margin-bottom: 2px;
    cursor: pointer;
  }
</style>
</head>
<body>

<div class="container">
  <div class="ring" id="ring">
    <svg viewBox="0 0 100 100">
      <circle class="ring-bg" cx="50" cy="50" r="44" />
      <circle class="ring-fill" id="ringFill" cx="50" cy="50" r="44" />
    </svg>
    <div class="time-display" id="timeDisplay">05:00</div>
  </div>

  <select class="sound-select" id="soundSelect"></select>

  <div class="hint" id="hint">click time to set · scroll ±1 min · space</div>
  <div class="row">
    <button class="btn btn-play" id="btnPlay">▶ Start</button>
    <button class="btn btn-reset" id="btnReset">↺ Reset</button>
  </div>
  <div class="row">
    <div class="count-pill" title="Completed countdowns — counts every time the timer reaches 00:00">
      <span class="count-label">count</span>
      <span id="countVal">0</span>
    </div>
    <button class="btn btn-count-reset" id="btnCountReset" title="Reset the count to 0">↺</button>
  </div>
  <div class="perhour" id="perHour"></div>
  <button class="btn btn-close" id="btnClose">✕ Close</button>
</div>

<script>
  const RING_R   = 44;
  const CIRC     = 2 * Math.PI * RING_R;
  const MAX_SEC  = 5999 * 60;           // ceiling kept from the old scroll cap (~99 h 59 m)
  const ringFill = document.getElementById('ringFill');
  ringFill.style.strokeDasharray = CIRC;

  let totalSec    = 300;
  let remaining   = totalSec;
  let running     = false;
  let startWall   = null;
  let stored      = totalSec;
  let _flashed    = false;   // only flash/alarm once per run
  let _flashTimer = null;    // timeout handle for the alarm flash loop
  let editInput   = null;    // the manual time-entry field when open
  let intervalCount = 0;     // completed countdowns (times the timer hit 00:00)

  const disp    = document.getElementById('timeDisplay');
  const hint    = document.getElementById('hint');
  const btnPlay = document.getElementById('btnPlay');
  const ring    = document.getElementById('ring');
  const countVal = document.getElementById('countVal');
  const perHour  = document.getElementById('perHour');

  // ── Sound selector ────────────────────────────────────
  const FALLBACK_SOUNDS = ['beep', 'chime', 'gentle', 'urgent'];

  function fillSounds(choices) {
    const sel = document.getElementById('soundSelect');
    for (const c of choices) {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      sel.appendChild(opt);
    }
    sel.value = 'chime';   // default matches the Python side
  }

  function initSounds() {
    const sel = document.getElementById('soundSelect');
    if (window.pywebview && window.pywebview.api) {
      pywebview.api.get_sound_choices()
        .then(fillSounds)
        .catch(() => fillSounds(FALLBACK_SOUNDS));
    } else {
      fillSounds(FALLBACK_SOUNDS);   // lets the HTML run in a plain browser too
    }
    sel.addEventListener('change', () => {
      if (window.pywebview && window.pywebview.api)
        pywebview.api.set_sound(sel.value);
    });
  }
  initSounds();

  function fmt(sec) {
    sec = Math.max(0, Math.floor(sec));
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    const mm = String(m).padStart(2, '0');
    const ss = String(s).padStart(2, '0');
    return h > 0 ? h + ':' + mm + ':' + ss : mm + ':' + ss;
  }

  // "24 × 2:30 in 1 hour" — how many of the set duration fit into 60 minutes
  function shortFmt(sec) {
    return fmt(sec).replace(/^0(?=\d)/, '');   // 02:30 → 2:30
  }

  function pieceCountStr(sec) {
    const raw = 3600 / sec;
    const r = Math.round(raw * 10) / 10;
    const n = Number.isInteger(r) ? String(r) : r.toFixed(1);
    return n + ' × ' + shortFmt(sec) + ' in 1 hour';
  }

  function refreshPerHour() {
    perHour.textContent = pieceCountStr(totalSec);
  }

  function resetCount() {
    intervalCount = 0;
    countVal.textContent = intervalCount;
  }

  function drawRing() {
    const ratio = totalSec ? Math.max(0, remaining / totalSec) : 0;
    ringFill.style.strokeDashoffset = CIRC - (ratio * CIRC);
  }

  function baseHint() {
    return running ? '' : 'click time to set · scroll ±1 min · space';
  }

  function draw() {
    disp.textContent = fmt(remaining);
    drawRing();
    hint.textContent = baseHint();
  }

  // ── Alarm flash: bounded ~3 s RGB cycle, stoppable on reset ──
  function stopFlash() {
    if (_flashTimer) { clearTimeout(_flashTimer); _flashTimer = null; }
    ring.classList.remove('flash-red', 'flash-blue', 'flash-green');
  }

  function flashSequence(i, cycles) {
    const colors = ['flash-red', 'flash-blue', 'flash-green'];
    ring.classList.remove(...colors);
    ring.classList.add(colors[i]);
    const next = (i + 1) % colors.length;
    if (cycles < 14) {
      _flashTimer = setTimeout(() => flashSequence(next, cycles + 1), 200);
    } else {
      _flashTimer = null;
    }
  }

  function endAlarm() {
    _flashed = true;
    flashSequence(0, 0);
    // background pulse
    let pulse = 0;
    const pulseColors = ['#ffcccc', '#ccccff', '#ddffdd', '#e2e4e6'];
    function bgPulse() {
      document.body.style.background = pulseColors[pulse % pulseColors.length];
      pulse++;
      if (pulse < 10) setTimeout(bgPulse, 300);
      else document.body.style.background = '';
    }
    bgPulse();
    // play sound via Python backend
    if (window.pywebview && window.pywebview.api) pywebview.api.play_alert();
  }

  function tick() {
    if (running) {
      const elapsed = (Date.now() / 1000) - startWall;
      remaining = Math.max(0, stored - elapsed);
    }
    draw();

    if (running && remaining <= 0 && !_flashed) {
      running = false;
      startWall = null;
      btnPlay.textContent = '▶ Start';
      intervalCount += 1;              // one completed countdown
      countVal.textContent = intervalCount;
      endAlarm();
    }
  }

  function startStop() {
    if (running) {
      const elapsed = (Date.now() / 1000) - startWall;
      stored = Math.max(0, stored - elapsed);
      remaining = stored;
      startWall = null;
      running = false;
      btnPlay.textContent = '▶ Start';
    } else {
      if (remaining <= 0) { reset(); _flashed = false; }  // finished → full restart
      stored = remaining;
      startWall = Date.now() / 1000;
      running = true;
      _flashed = false;
      btnPlay.textContent = '⏸ Pause';
    }
    draw();
  }

  function reset() {
    setDuration(totalSec);
  }

  // ── Single writer for the duration: always leaves a fresh, stopped timer ──
  function setDuration(secs) {
    stopFlash();
    totalSec   = secs;
    remaining  = secs;
    stored     = secs;
    startWall  = null;
    running    = false;
    _flashed   = false;
    btnPlay.textContent = '▶ Start';
    document.body.style.background = '';
    refreshPerHour();          // duration changed → pieces-per-hour figure too
    draw();
  }

  // ── Time adjustment (scroll / arrows) ──────────────────
  function clampSec(v) { return Math.max(1, Math.min(MAX_SEC, Math.round(v))); }

  function adjust(deltaSec) {
    if (running || editInput) return;   // never change the time mid-run or while typing
    setDuration(clampSec(totalSec + deltaSec));
  }

  document.addEventListener('wheel', function(e) {
    if (editInput) return;              // don't fight the keyboard while typing
    e.preventDefault();
    const notch = e.deltaY < 0 ? 1 : -1;
    adjust(e.shiftKey ? notch * 5       // Shift+wheel → ±5 s fine steps
                      : notch * 60);    // wheel       → ±1 min
  }, { passive: false });

  document.addEventListener('keydown', function(e) {
    if (editInput) return;              // typing — let the field handle keys
    if (e.key === ' ')          { startStop(); e.preventDefault(); }
    if (e.key === 'Backspace')  { reset();     e.preventDefault(); }
    if (e.key === 'ArrowUp')    { adjust(e.shiftKey ? 1 : 60);   e.preventDefault(); }
    if (e.key === 'ArrowDown')  { adjust(e.shiftKey ? -1 : -60); e.preventDefault(); }
    if (e.key === 'Escape') {
      if (window.pywebview && window.pywebview.api) pywebview.api.close_window();
      e.preventDefault();
    }
  });

  // ── Manual time entry ──────────────────────────────────
  // Accepted forms: "25" (minutes) · "2.5" · "1:30" · "90:00" · "1:30:00"
  //                 "90s" · "25m" · "2h" · "1h30m20s" · "0.5h"
  function parseTime(raw) {
    const s = String(raw).trim().toLowerCase().replace(/\s+/g, '');
    if (!s) return null;
    let total = null;

    // compound units: 90s · 25m · 2h · 1h30m · 1h30m20s
    const u = s.match(/^(\d+(?:\.\d+)?h)?(\d+(?:\.\d+)?m)?(\d+(?:\.\d+)?s)?$/);
    if (u && (u[1] || u[2] || u[3])) {
      total = (u[1] ? parseFloat(u[1]) * 3600 : 0)
            + (u[2] ? parseFloat(u[2]) * 60 : 0)
            + (u[3] ? parseFloat(u[3]) : 0);
    }

    if (total === null) {
      const parts = s.split(':');
      if (parts.length === 1) {
        // bare number = minutes, matching the scroll behaviour ("25" = 25 min)
        if (/^\d+(?:\.\d+)?$/.test(s)) total = parseFloat(s) * 60;
      } else if (parts.length === 2 || parts.length === 3) {
        // mm:ss (minutes may exceed 59) or h:mm:ss — seconds field must be < 60
        const ok = parts.every(p => /^\d{1,4}$/.test(p));
        if (ok) {
          const nums = parts.map(Number);
          const sec  = nums[nums.length - 1];
          const min  = nums[nums.length - 2];
          if (sec < 60 && (parts.length === 2 || min < 60)) {
            total = (parts.length === 3 ? nums[0] * 3600 : 0) + min * 60 + sec;
          }
        }
      }
    }

    if (total === null || !isFinite(total)) return null;
    const secs = Math.round(total);
    return secs >= 1 ? clampSec(secs) : null;
  }

  function beginEdit() {
    if (editInput) return;
    if (running) startStop();           // pause first — a typed value sets a fresh timer
    disp.style.display = 'none';
    editInput = document.createElement('input');
    editInput.type = 'text';
    editInput.className = 'time-edit';
    editInput.value = fmt(totalSec);    // prefill current time, ready to overwrite
    editInput.setAttribute('inputmode', 'decimal');
    editInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter')       { endEdit(true);  e.preventDefault(); }
      else if (e.key === 'Escape') { endEdit(false); e.preventDefault(); }
    });
    editInput.addEventListener('blur', () => endEdit(true));   // click away = commit
    ring.appendChild(editInput);
    hint.textContent = 'set time: 25 min · 1:30 · 90s · Enter';
    editInput.focus();
    editInput.select();
  }

  function endEdit(commit) {
    if (!editInput) return;
    const val = editInput.value;
    editInput.remove();
    editInput = null;
    disp.style.display = '';
    if (commit) {
      const secs = parseTime(val);
      if (secs !== null) setDuration(secs);   // invalid input keeps the old time
    }
    hint.textContent = baseHint();
    draw();
  }

  // ── Wiring ─────────────────────────────────────────────
  btnPlay.addEventListener('click', startStop);
  document.getElementById('btnReset').addEventListener('click', reset);
  document.getElementById('btnCountReset').addEventListener('click', resetCount);
  document.getElementById('btnClose').addEventListener('click', () => {
    if (window.pywebview && window.pywebview.api) pywebview.api.close_window();
  });
  // Clicking the digits opens the editor; the ring itself still starts the timer
  disp.addEventListener('click', (e) => { e.stopPropagation(); beginEdit(); });
  document.getElementById('ring').addEventListener('click', () => {
    if (editInput) return;              // blur above already committed the typed time
    if (!running) startStop();
  });

  setInterval(tick, 100);
  draw();
  tick();
  refreshPerHour();
</script>
</body>
</html>
"""

def _set_window_opacity(alpha=128, title="Timer"):
    """Make the top-level window translucent via WS_EX_LAYERED + uniform alpha.

    Unlike pywebview's per-pixel transparent mode (which does not take effect
    with the WebView2 backend on this machine), this is a plain Win32 layered
    window: DWM fades the entire composited window, browser included.
    alpha: 0 = fully invisible … 255 = fully opaque (128 ≈ 50%).
    """
    import ctypes
    import ctypes.wintypes as wt
    import time

    user32 = ctypes.windll.user32

    def _find():
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            return hwnd
        # Frameless windows can be missed by FindWindowW — fall back to
        # enumerating all top-level windows and matching title + visibility.
        found = []

        @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        def _cb(h, _l):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(h, buf, 256)
            if buf.value == title and user32.IsWindowVisible(h):
                found.append(h)
            return True

        user32.EnumWindows(_cb, 0)
        return found[0] if found else None

    hwnd = None
    for _ in range(50):                      # wait up to ~10 s for the window
        hwnd = _find()
        if hwnd:
            break
        time.sleep(0.2)
    if not hwnd:
        return

    GWL_EXSTYLE, WS_EX_LAYERED, LWA_ALPHA = -20, 0x00080000, 0x2
    ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED)
    user32.SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA)


if __name__ == "__main__":
    api = TimerAPI()
    window = webview.create_window(
        title="Timer",
        html=HTML,
        js_api=api,
        width=200,
        height=320,
        resizable=False,
        frameless=True,
        on_top=True,
    )
    api.set_window(window)

    # Apply ~75% window opacity (runs on its own thread; webview.start()
    # blocks until the app closes, but the native window appears quickly).
    import threading
    threading.Thread(
        target=_set_window_opacity,
        kwargs={"alpha": 191, "title": "Timer"},
        daemon=True,
    ).start()

    webview.start()  # auto-detect best GUI backend
