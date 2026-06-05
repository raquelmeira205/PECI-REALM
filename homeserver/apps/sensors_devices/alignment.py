import numpy as np
from scipy.optimize import minimize

from core.geometry.room_geometry import radar_to_room
from core.parsing.data_filter import filter_frames, select_dominant_blob


# ---------------------------------------------------------------------------
# Helpers de integração Django
# ---------------------------------------------------------------------------

def _build_radar_cfg(radar):
    """
    Constrói o dict de configuração compatível com radar_to_room() a partir
    de uma instância do modelo Radar.
    """
    return {
        "position_m": {
            "x": float(radar.pos_x),
            "y": float(radar.pos_y),
            "z": float(radar.pos_z),
        },
        "azimuth_deg": float(radar.azimuth_deg),
        "tilt_deg":    float(radar.tilt_deg),
    }


def run_alignment(master_sn, slaves, start_time, end_time):
    """
    Orquestra o alinhamento espacial de um ou mais radares slave em relação
    ao radar master, usando os dados capturados na janela [start_time, end_time].

    Parâmetros
    ----------
    master_sn  : str               — network_id do radar master
    slaves     : list[Radar]       — instâncias do modelo Radar slave
    start_time : datetime (UTC)    — início da janela de captura
    end_time   : datetime (UTC)    — fim da janela de captura

    Retorna
    -------
    list[dict] com um resultado por slave:
      {'radar': str, 'azimuth': float, 'tilt': float, 'mse': float, 'offset_ms': float}
      ou {'radar': str, 'error': str} em caso de falha.
    """
    from sensors_devices.models import Radar
    from sensors_devices.utils import get_radar_frames_for_alignment

    master        = Radar.objects.get(network_id=master_sn)
    master_cfg    = _build_radar_cfg(master)
    master_frames = get_radar_frames_for_alignment(master_sn, start_time, end_time)

    results = []
    for slave in slaves:
        slave_cfg    = _build_radar_cfg(slave)
        slave_frames = get_radar_frames_for_alignment(slave.network_id, start_time, end_time)

        if not master_frames or not slave_frames:
            results.append({"radar": slave.network_id, "error": "Sem dados de captura"})
            continue

        aligner = SpatialAligner(master_cfg, slave_cfg)
        best_az, best_tilt, mse, offset_ms = aligner.run_alignment(master_frames, slave_frames)

        slave.azimuth_deg   = best_az
        slave.tilt_deg      = best_tilt
        slave.is_calibrated = True
        slave.save(update_fields=["azimuth_deg", "tilt_deg", "is_calibrated"])

        results.append({
            "radar":     slave.network_id,
            "azimuth":   round(best_az, 2),
            "tilt":      round(best_tilt, 2),
            "mse":       round(mse, 4),
            "offset_ms": round(offset_ms, 1),
        })

    return results


def transform_radar_points(raw_points, radar):
    """
    Transforma uma lista de pontos [x, y, z] do referencial local do radar
    para o referencial da sala, devolvendo apenas as coordenadas [x, y].

    Parâmetros
    ----------
    raw_points : list[[x, y, z]]  — output de get_radar_calibration_snapshot()
    radar      : Radar            — instância do modelo Radar

    Retorna
    -------
    list[[x, y]] no referencial da sala.
    """
    if not raw_points:
        return []
    pts      = np.array(raw_points, dtype=float)
    cfg      = _build_radar_cfg(radar)
    room_pts = radar_to_room(pts, cfg)
    return room_pts[:, :2].tolist()


# ---------------------------------------------------------------------------
# Funções auxiliares de sliding windows (replicadas do calibrator_auto.py)
# ---------------------------------------------------------------------------

def sliding_windows(frames_pc, win_size, step):
    """
    Gera janelas de tempo sobre uma lista de Point Clouds filtradas.
    Cada janela agrega os pontos de `win_size` frames consecutivas,
    avançando `step` frames de cada vez.

    Parâmetros
    ----------
    frames_pc : list[np.ndarray]  – lista de arrays (N, >=3) por frame
    win_size  : int               – número de frames por janela
    step      : int               – avanço entre janelas consecutivas

    Yields
    ------
    np.ndarray  – pontos agregados da janela (M, 5) ou (0, 5)
    """
    n = len(frames_pc)
    for start in range(0, n - win_size + 1, step):
        chunk = [frames_pc[start + i] for i in range(win_size)]
        non_empty = [c for c in chunk if c.shape[0] > 0]
        if non_empty:
            yield np.vstack(non_empty)
        else:
            yield np.empty((0, 5))


def _calc_frame_rate(frames, default=10.0):
    """
    Calcula a frame rate real a partir de `absolute_timestamp_sec`.
    Se os timestamps não estiverem disponíveis faz fallback para `default` Hz.
    """
    ts = [fr.get("absolute_timestamp_sec") for fr in frames
          if fr.get("absolute_timestamp_sec") is not None]
    if len(ts) >= 2:
        duration = ts[-1] - ts[0]
        if duration > 0:
            rate = (len(ts) - 1) / duration
            print(f"   Frame rate medida: {rate:.2f} Hz  ({len(ts)} frames, {duration:.2f}s)")
            return rate
    print(f"   [aviso] Timestamps não disponíveis. A usar frame rate por defeito: {default} Hz")
    return default


# ---------------------------------------------------------------------------
# Motor principal de alinhamento
# ---------------------------------------------------------------------------

class SpatialAligner:
    """
    Motor matemático puro que calcula as correções angulares (Azimute e Tilt)
    de um radar Slave para coincidir com a trajetória captada pelo radar Master.

    Fluxo interno (espelha o calibrator_auto.py):
      1. Filtrar frames por Doppler mínimo.
      2. Segmentar em janelas de tempo (0.5 s, step 0.25 s).
      3. Extrair blob dominante de cada janela.
      4. Estimar offset temporal (timestamps reais ou cross-correlation).
      5. Vector Walk → azimute inicial.
      6. Otimização Nelder-Mead (MSE dos centros).
    """

    def __init__(self, master_cfg, slave_cfg_base):
        """
        Parâmetros
        ----------
        master_cfg     : dict – configuração completa do radar master
                                (mesmo formato do room_config.json)
        slave_cfg_base : dict – configuração inicial do radar slave
        """
        self.master_cfg     = master_cfg
        self.slave_cfg_base = slave_cfg_base

    # ------------------------------------------------------------------
    # Fase 1 – preparação das janelas
    # ------------------------------------------------------------------

    def _build_windows(self, frames_raw, radar_cfg, min_doppler=0.25):
        """
        A partir das frames brutas (lista de dicts com 'pointCloud' e
        'absolute_timestamp_sec'), devolve:
          - centers_room  : lista de centros [X,Y] no ref. sala (ou None)
          - raw_windows   : lista de np.ndarray (N,3) XYZ locais (slave)
          - speeds        : lista de velocidades médias por janela (Doppler)
          - frame_rate    : Hz medido
        """
        # Extrair point clouds (N,5) por frame
        pc_frames = []
        for fr in frames_raw:
            pc = np.array(fr.get("pointCloud", []), dtype=float)
            if pc.ndim == 2 and pc.shape[0] > 0 and pc.shape[1] >= 5:
                pc_frames.append(pc[:, :5])
            else:
                pc_frames.append(np.empty((0, 5)))

        # Filtrar Doppler
        pc_filt = filter_frames(pc_frames, min_doppler=min_doppler)

        # Frame rate real
        frame_rate = _calc_frame_rate(frames_raw)
        win_size_f = max(1, int(0.5 * frame_rate))
        win_step_f = max(1, int(0.25 * frame_rate))

        centers = []
        raw_windows = []
        speeds = []

        for win_pts in sliding_windows(pc_filt, win_size_f, win_step_f):
            if win_pts.shape[0] > 0:
                room = radar_to_room(win_pts[:, :3], radar_cfg)
                mask, center = select_dominant_blob(room[:, :2])
                centers.append(center)
                raw_windows.append(win_pts[:, :3])
                speeds.append(np.mean(np.abs(win_pts[mask, 3])) if np.any(mask) else 0.0)
            else:
                centers.append(None)
                raw_windows.append(np.empty((0, 3)))
                speeds.append(0.0)

        return centers, raw_windows, speeds, frame_rate

    # ------------------------------------------------------------------
    # Fase 3 – offset temporal
    # ------------------------------------------------------------------

    def _estimate_time_offset(self, frames1, frames2, w1_speeds, w2_speeds, frame_rate, win_step_f):
        """
        Método 1: Timestamps reais (mais fiável, ficheiros .jsonl).
        Método 2: Cross-Correlation das velocidades (fallback .json antigo).

        Devolve o offset em milissegundos (float).
        """
        ts1 = [fr.get("absolute_timestamp_sec") for fr in frames1
               if fr.get("absolute_timestamp_sec") is not None]
        ts2 = [fr.get("absolute_timestamp_sec") for fr in frames2
               if fr.get("absolute_timestamp_sec") is not None]

        if ts1 and ts2:
            offset_ms = (ts2[0] - ts1[0]) * 1000.0
            print(f"   Offset real dos timestamps: {offset_ms:.1f} ms")
            return offset_ms

        # Fallback: cross-correlation
        vel1 = np.array(w1_speeds)
        vel2 = np.array(w2_speeds)
        max_lag = max(1, int(0.5 / (win_step_f / frame_rate)))  # ±500 ms

        if np.std(vel1) > 0 and np.std(vel2) > 0:
            v1_n = vel1 - np.mean(vel1)
            v2_n = vel2 - np.mean(vel2)
            corr = np.correlate(v1_n, v2_n, mode='full')
            center = len(v2_n) - 1
            lo = max(0, center - max_lag)
            hi = min(len(corr), center + max_lag + 1)
            lag = np.argmax(corr[lo:hi]) + lo - center
            offset_s = lag * (win_step_f / frame_rate)
            offset_ms = offset_s * 1000.0
            print(f"   Lag estimado (cross-corr) = {lag} janelas -> Offset: {offset_ms:.1f} ms")
            return offset_ms

        print("   [Aviso] Variância de velocidade insuficiente. Offset mantido a 0 ms.")
        return 0.0

    # ------------------------------------------------------------------
    # Fase 2 – Vector Walk (azimute inicial)
    # ------------------------------------------------------------------

    def estimate_initial_azimuth(self, master_centers, slave_centers):
        """
        Vector Walk: Estima um azimute inicial razoável para evitar mínimos locais.
        Os centros do slave são no referencial LOCAL do radar (antes de radar_to_room).
        """
        valid = [(c1, c2) for c1, c2 in zip(master_centers, slave_centers)
                 if c1 is not None and c2 is not None]
        if len(valid) < 2:
            print("   [Aviso] Janelas válidas insuficientes para Vector Walk. A usar 0°.")
            return self.slave_cfg_base.get("azimuth_deg", 0.0)

        c1_start, c2_start = valid[0]
        c1_end,   c2_end   = valid[-1]

        theta_1 = np.degrees(np.arctan2(c1_end[0] - c1_start[0], c1_end[1] - c1_start[1]))
        theta_2 = np.degrees(np.arctan2(c2_end[0] - c2_start[0], c2_end[1] - c2_start[1]))

        delta_theta = (theta_1 - theta_2 + 180) % 360 - 180
        print(f"   Vetor R1: {theta_1:.1f}°, Vetor R2: {theta_2:.1f}° -> Azimute Inicial Estimado: {delta_theta:.1f}°")
        return delta_theta

    # ------------------------------------------------------------------
    # Fase 4 – Otimização Nelder-Mead
    # ------------------------------------------------------------------

    def _cost_function(self, params, master_centers, slave_raw_windows):
        az, tilt = params
        temp_cfg = self.slave_cfg_base.copy()
        temp_cfg["azimuth_deg"] = float(az)
        temp_cfg["tilt_deg"]    = float(tilt)

        err   = 0.0
        count = 0
        for c_master, pts_slave in zip(master_centers, slave_raw_windows):
            if c_master is not None and pts_slave.shape[0] > 0:
                room_pts = radar_to_room(pts_slave, temp_cfg)
                _, c_slave = select_dominant_blob(room_pts[:, :2])
                if c_slave is not None:
                    err += np.sum((c_master - c_slave) ** 2)
                    count += 1
        return err / count if count > 0 else float('inf')

    # ------------------------------------------------------------------
    # Interface pública principal
    # ------------------------------------------------------------------

    def run_alignment(self, master_frames_raw, slave_frames_raw, min_doppler=0.25):
        """
        Executa o pipeline completo de alinhamento espacial.

        Parâmetros
        ----------
        master_frames_raw : list[dict]  – frames brutas do radar master
                                          (cada dict tem 'pointCloud' e
                                          opcionalmente 'absolute_timestamp_sec')
        slave_frames_raw  : list[dict]  – idem para o radar slave
        min_doppler       : float       – limiar de filtragem Doppler (m/s)

        Retorna
        -------
        best_az        : float  – azimute otimizado (graus)
        best_tilt      : float  – tilt otimizado (graus)
        mse_final      : float  – erro quadrático médio final (m²)
        time_offset_ms : float  – offset temporal estimado entre radares (ms)
        """
        print("-> A filtrar e segmentar janelas do Master...")
        master_centers, _, master_speeds, frame_rate = self._build_windows(
            master_frames_raw, self.master_cfg, min_doppler
        )

        if all(c is None for c in master_centers):
            raise RuntimeError("O radar Master não detetou nenhuma pessoa (nenhum blob válido)!")

        print("-> A filtrar e segmentar janelas do Slave (pontos brutos)...")
        _, slave_raw_windows, slave_speeds, _ = self._build_windows(
            slave_frames_raw, self.slave_cfg_base, min_doppler
        )

        # Calcular tamanho de janela para a cross-correlation (fallback)
        win_step_f = max(1, int(0.25 * frame_rate))

        print("-> A estimar Offset temporal entre os dois radares...")
        time_offset_ms = self._estimate_time_offset(
            master_frames_raw, slave_frames_raw,
            master_speeds, slave_speeds,
            frame_rate, win_step_f
        )

        # Centros brutos do Slave (referencial local) para o Vector Walk
        slave_centers_raw = []
        for pts in slave_raw_windows:
            if pts.shape[0] > 0:
                _, center = select_dominant_blob(pts[:, :2])
                slave_centers_raw.append(center)
            else:
                slave_centers_raw.append(None)

        print("-> A calcular Vector Walk inicial...")
        init_az   = self.estimate_initial_azimuth(master_centers, slave_centers_raw)
        init_tilt = self.slave_cfg_base.get("tilt_deg", 0.0)

        n = min(len(master_centers), len(slave_raw_windows))
        print(f"-> A iniciar Otimização Nelder-Mead sobre as {n} janelas de tempo...")
        res = minimize(
            self._cost_function,
            x0=[init_az, init_tilt],
            args=(master_centers[:n], slave_raw_windows[:n]),
            method='Nelder-Mead',
            options={'maxiter': 500}
        )

        best_az, best_tilt = res.x
        mse_final = res.fun

        print(f"\n[SUCESSO] Otimização concluída. Erro nos Centros = {mse_final:.4f} m²")
        print(f"   NOVO Azimuth = {best_az:.2f}°")
        print(f"   NOVO Tilt    = {best_tilt:.2f}°")
        print(f"   Offset temporal = {time_offset_ms:.1f} ms")

        return best_az, best_tilt, mse_final, time_offset_ms