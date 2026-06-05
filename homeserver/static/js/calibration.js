/**
 * calibration.js
 * --------------
 * Porta fiel de room_geometry.py para o browser.
 *
 * Convenção de ângulos (igual ao Python):
 *   azimuth_deg : 0°=+Y, 90°=+X, 180°=-Y, 270°=-X (horário)
 *   tilt_deg    : 0°=vertical (chão), 90°=horizontal
 *
 * Utilização:
 *   const cal = new RadarCalibrator('canvas-id', roomBounds, radarConfig, rawPoints);
 *   cal.render();
 */

// ---------------------------------------------------------------------------
// Transform: referencial do radar → referencial da sala
// Porta exata de radar_to_room() em room_geometry.py
// ---------------------------------------------------------------------------
function radarToRoom(points, radarCfg) {
  const { x: rx, y: ry, z: rz } = radarCfg.position_m;
  const azRad   = (radarCfg.azimuth_deg  * Math.PI) / 180;
  const tiltRad = (radarCfg.tilt_deg     * Math.PI) / 180;

  const cosAz = Math.cos(azRad);
  const sinAz = Math.sin(azRad);
  const sinT  = Math.sin(tiltRad);
  const cosT  = Math.cos(tiltRad);

  return points.map(([xr, yr, zr]) => ({
    x: rx + xr * cosAz       + yr * sinAz * sinT,
    y: ry - xr * sinAz       + yr * cosAz * sinT,
    z: rz                    - yr * cosT  + zr,
  }));
}

// ---------------------------------------------------------------------------
// RadarCalibrator — classe principal
// ---------------------------------------------------------------------------
class RadarCalibrator {
  /**
   * @param {string}   canvasId    — id do elemento <canvas>
   * @param {object}   roomBounds  — { x_max, y_max }  (metros)
   * @param {object}   radarCfg    — { position_m:{x,y,z}, azimuth_deg, tilt_deg }
   * @param {Array}    rawPoints   — [[x,y,z], ...] no referencial do radar
   */
  constructor(canvasId, roomBounds, radarCfg, rawPoints) {
    this.canvas     = document.getElementById(canvasId);
    this.ctx        = this.canvas.getContext('2d');
    this.roomBounds = roomBounds;
    this.radarCfg   = structuredClone(radarCfg);
    this.rawPoints  = rawPoints;
    this.referencePoint = null; // { x, y } em coordenadas de sala

    this._padding   = 40;
    this._scale     = 1;
  }

  // ── API pública ────────────────────────────────────────────────────────

  /** Actualiza um parâmetro de calibração e redesenha. */
  update(param, value) {
    const num = parseFloat(value);
    if (isNaN(num)) return;
    switch (param) {
      case 'azimuth':  this.radarCfg.azimuth_deg        = num; break;
      case 'tilt':     this.radarCfg.tilt_deg            = num; break;
      case 'pos_x':    this.radarCfg.position_m.x        = num; break;
      case 'pos_y':    this.radarCfg.position_m.y        = num; break;
      case 'pos_z':    this.radarCfg.position_m.z        = num; break;
    }
    this.render();
  }

  /** Define o ponto de referência em coordenadas de sala e redesenha. */
  setReferencePoint(x, y) {
    const px = parseFloat(x);
    const py = parseFloat(y);
    if (isNaN(px) || isNaN(py)) return;
    this.referencePoint = { x: px, y: py };
    this.render();
  }

  /** Devolve os parâmetros actuais (para enviar ao backend). */
  getCalibration() {
    return {
      azimuth:  this.radarCfg.azimuth_deg,
      tilt:     this.radarCfg.tilt_deg,
      x:        this.radarCfg.position_m.x,
      y:        this.radarCfg.position_m.y,
      z:        this.radarCfg.position_m.z,
    };
  }

  /** Redesenha o canvas completo. */
  render() {
    const { canvas, ctx, roomBounds, _padding: pad } = this;
    const W = canvas.width;
    const H = canvas.height;

    const scaleX = (W - 2 * pad) / roomBounds.x_max;
    const scaleY = (H - 2 * pad) / roomBounds.y_max;
    this._scale  = Math.min(scaleX, scaleY);

    ctx.clearRect(0, 0, W, H);
    this._drawRoom();
    this._drawPoints();
    this._drawCentroid();
    this._drawReferencePoint();
    this._drawRadar();
  }

  // ── Métodos privados ────────────────────────────────────────────────────

  /** Converte metros (sala) → pixels no canvas. */
  _toCanvas(xm, ym) {
    const { _padding: pad, _scale: s, roomBounds, canvas } = this;
    const offsetX = (canvas.width  - 2 * pad - roomBounds.x_max * s) / 2;
    const offsetY = (canvas.height - 2 * pad - roomBounds.y_max * s) / 2;
    return {
      px: pad + offsetX + xm * s,
      py: canvas.height - pad - offsetY - ym * s,
    };
  }

  _drawRoom() {
    const { ctx, roomBounds } = this;
    const tl = this._toCanvas(0,               roomBounds.y_max);
    const br = this._toCanvas(roomBounds.x_max, 0);
    const w  = br.px - tl.px;
    const h  = br.py - tl.py;

    ctx.fillStyle   = 'rgba(30, 58, 95, 0.15)';
    ctx.fillRect(tl.px, tl.py, w, h);

    ctx.strokeStyle = '#3b82f6';
    ctx.lineWidth   = 2;
    ctx.strokeRect(tl.px, tl.py, w, h);

    ctx.strokeStyle = 'rgba(100, 130, 180, 0.2)';
    ctx.lineWidth   = 0.5;
    for (let x = 1; x < roomBounds.x_max; x++) {
      const a = this._toCanvas(x, 0);
      const b = this._toCanvas(x, roomBounds.y_max);
      ctx.beginPath(); ctx.moveTo(a.px, a.py); ctx.lineTo(b.px, b.py); ctx.stroke();
    }
    for (let y = 1; y < roomBounds.y_max; y++) {
      const a = this._toCanvas(0,               y);
      const b = this._toCanvas(roomBounds.x_max, y);
      ctx.beginPath(); ctx.moveTo(a.px, a.py); ctx.lineTo(b.px, b.py); ctx.stroke();
    }

    ctx.fillStyle  = '#94a3b8';
    ctx.font       = '11px monospace';
    ctx.textAlign  = 'center';
    const bBot = this._toCanvas(roomBounds.x_max / 2, 0);
    ctx.fillText(`${roomBounds.x_max.toFixed(2)} m`, bBot.px, bBot.py + 18);
    ctx.save();
    ctx.translate(tl.px - 18, tl.py + h / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(`${roomBounds.y_max.toFixed(2)} m`, 0, 0);
    ctx.restore();
  }

  _drawPoints() {
    if (!this.rawPoints || this.rawPoints.length === 0) return;
    const { ctx } = this;
    const transformed = radarToRoom(this.rawPoints, this.radarCfg);

    ctx.fillStyle = 'rgba(52, 211, 153, 0.55)';
    for (const pt of transformed) {
      if (pt.x < -0.5 || pt.x > this.roomBounds.x_max + 0.5) continue;
      if (pt.y < -0.5 || pt.y > this.roomBounds.y_max + 0.5) continue;
      const { px, py } = this._toCanvas(pt.x, pt.y);
      ctx.beginPath();
      ctx.arc(px, py, 2.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  /** Calcula o centróide dos pontos transformados dentro dos bounds da sala. */
  _computeCentroid() {
    if (!this.rawPoints || this.rawPoints.length === 0) return null;
    const transformed = radarToRoom(this.rawPoints, this.radarCfg);
    const inside = transformed.filter(pt =>
      pt.x >= -0.5 && pt.x <= this.roomBounds.x_max + 0.5 &&
      pt.y >= -0.5 && pt.y <= this.roomBounds.y_max + 0.5
    );
    if (inside.length === 0) return null;
    const sumX = inside.reduce((s, p) => s + p.x, 0);
    const sumY = inside.reduce((s, p) => s + p.y, 0);
    return { x: sumX / inside.length, y: sumY / inside.length };
  }

  /** Desenha o centróide da nuvem como um círculo laranja com cruz. */
  _drawCentroid() {
    const c = this._computeCentroid();
    if (!c) return;
    const { px, py } = this._toCanvas(c.x, c.y);
    const { ctx } = this;
    const r = 7;
    const arm = 12;

    ctx.strokeStyle = '#fb923c';
    ctx.lineWidth   = 1.5;
    ctx.beginPath(); ctx.moveTo(px - arm, py); ctx.lineTo(px + arm, py); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(px, py - arm); ctx.lineTo(px, py + arm); ctx.stroke();

    ctx.strokeStyle = '#fb923c';
    ctx.lineWidth   = 2;
    ctx.beginPath();
    ctx.arc(px, py, r, 0, Math.PI * 2);
    ctx.stroke();

    ctx.fillStyle    = '#fb923c';
    ctx.font         = '10px monospace';
    ctx.textAlign    = 'left';
    ctx.textBaseline = 'bottom';
    ctx.fillText(`(${c.x.toFixed(2)}, ${c.y.toFixed(2)})`, px + r + 3, py - 2);
  }

  /** Desenha a mira de referência (⊕) em vermelho. */
  _drawReferencePoint() {
    if (!this.referencePoint) return;
    const { px, py } = this._toCanvas(this.referencePoint.x, this.referencePoint.y);
    const { ctx } = this;
    const r   = 10;
    const arm = 18;

    ctx.strokeStyle = '#f87171';
    ctx.lineWidth   = 1.5;
    ctx.beginPath(); ctx.moveTo(px - arm, py); ctx.lineTo(px + arm, py); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(px, py - arm); ctx.lineTo(px, py + arm); ctx.stroke();

    ctx.strokeStyle = '#f87171';
    ctx.lineWidth   = 2;
    ctx.beginPath();
    ctx.arc(px, py, r, 0, Math.PI * 2);
    ctx.stroke();

    ctx.fillStyle    = '#f87171';
    ctx.font         = '10px monospace';
    ctx.textAlign    = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(`ref (${this.referencePoint.x.toFixed(2)}, ${this.referencePoint.y.toFixed(2)})`, px + r + 3, py + 2);
  }

  _drawRadar() {
    const { ctx, radarCfg } = this;
    const { px, py } = this._toCanvas(radarCfg.position_m.x, radarCfg.position_m.y);

    ctx.fillStyle   = '#fbbf24';
    ctx.font        = '18px sans-serif';
    ctx.textAlign   = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('★', px, py);

    const azRad  = (radarCfg.azimuth_deg * Math.PI) / 180;
    const arrowL = 40;
    const dx     =  Math.sin(azRad) * arrowL;
    const dy     = -Math.cos(azRad) * arrowL;
    ctx.strokeStyle = '#fbbf24';
    ctx.lineWidth   = 2;
    ctx.beginPath();
    ctx.moveTo(px, py);
    ctx.lineTo(px + dx, py + dy);
    ctx.stroke();

    ctx.fillStyle = '#fbbf24';
    ctx.beginPath();
    ctx.arc(px + dx, py + dy, 4, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle    = '#fbbf24';
    ctx.font         = '11px monospace';
    ctx.textBaseline = 'top';
    ctx.fillText('Radar (master)', px + 10, py - 20);
  }
}

// ---------------------------------------------------------------------------
// Inicialização da página de calibração
// ---------------------------------------------------------------------------
function initCalibration() {
  const data = window.CALIBRATION_DATA;
  if (!data) return;

  const roomBounds = {
    x_max: data.room.x_max,
    y_max: data.room.y_max,
  };

  const radarCfg = {
    position_m:  { x: data.radar_current_config.x,
                   y: data.radar_current_config.y,
                   z: data.radar_current_config.z },
    azimuth_deg: data.radar_current_config.azimuth,
    tilt_deg:    data.radar_current_config.tilt,
  };

  window.cal = new RadarCalibrator(
    'calibration-canvas',
    roomBounds,
    radarCfg,
    data.raw_points
  );

  function resizeCanvas() {
    const container = document.getElementById('canvas-container');
    cal.canvas.width  = container.clientWidth;
    cal.canvas.height = container.clientWidth * 0.65;
    cal.render();
  }
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);

  // ── Sliders ───────────────────────────────────────────────────────────
  const sliders = [
    { id: 'slider-azimuth', param: 'azimuth',  display: 'val-azimuth',  unit: '°'  },
    { id: 'slider-tilt',    param: 'tilt',     display: 'val-tilt',     unit: '°'  },
  ];

  for (const { id, param, display, unit } of sliders) {
    const slider  = document.getElementById(id);
    const valSpan = document.getElementById(display);
    if (!slider) continue;

    slider.addEventListener('input', () => {
      valSpan.textContent = parseFloat(slider.value).toFixed(2) + unit;
      cal.update(param, slider.value);
    });
  }

  // ── Inputs numéricos ──────────────────────────────────────────────────
  const inputs = [
    { id: 'input-azimuth', param: 'azimuth', sliderId: 'slider-azimuth' },
    { id: 'input-tilt',    param: 'tilt',    sliderId: 'slider-tilt'    },
    { id: 'input-x',       param: 'pos_x',   sliderId: null             },
    { id: 'input-y',       param: 'pos_y',   sliderId: null             },
    { id: 'input-z',       param: 'pos_z',   sliderId: null             },
  ];

  for (const { id, param, sliderId } of inputs) {
    const inp    = document.getElementById(id);
    const slider = document.getElementById(sliderId);
    if (!inp) continue;
    inp.addEventListener('change', () => {
      cal.update(param, inp.value);
      if (slider) slider.value = inp.value;
    });
  }

  // ── Botão Guardar ──────────────────────────────────────────────────────
  const btnSave = document.getElementById('btn-save-calibration');
  if (btnSave) {
    btnSave.addEventListener('click', async () => {
      const payload   = cal.getCalibration();
      const radarSn   = btnSave.dataset.radarSn;
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

      btnSave.disabled    = true;
      btnSave.textContent = 'A guardar...';

      try {
        const res = await fetch(`/deployment/api/calibration/${radarSn}/save/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken':   csrfToken,
          },
          body: JSON.stringify(payload),
        });
        const json = await res.json();
        if (json.status === 'success') {
          btnSave.textContent  = '✅ Guardado!';
          btnSave.classList.replace('bg-emerald-600', 'bg-emerald-800');
          setTimeout(() => {
            htmx.ajax('GET', '/deployment/api/step3/', { target: '#wizard-content', swap: 'innerHTML' });
          }, 1200);
        } else {
          btnSave.textContent = '❌ Erro ao guardar';
          btnSave.disabled    = false;
        }
      } catch {
        btnSave.textContent = '❌ Erro de rede';
        btnSave.disabled    = false;
      }
    });
  }

  // ── Botão Atualizar pontos ─────────────────────────────────────────────
  const btnRefresh = document.getElementById('btn-refresh-points');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', async () => {
      const radarSn = btnRefresh.dataset.radarSn;
      const roomId  = btnRefresh.dataset.roomId;
      btnRefresh.textContent = '⟳ A carregar...';

      try {
        const res  = await fetch(`/deployment/api/calibration-context/${roomId}/${radarSn}/`);
        const json = await res.json();
        cal.rawPoints = json.raw_points;
        cal.render();
        btnRefresh.textContent = '⟳ Atualizar pontos';
      } catch {
        btnRefresh.textContent = '❌ Erro';
      }
    });
  }
}

// Funciona no carregamento normal e após injecção via HTMX (DOMContentLoaded já disparou)
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initCalibration);
} else {
  initCalibration();
}
