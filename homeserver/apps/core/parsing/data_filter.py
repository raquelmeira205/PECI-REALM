import numpy as np

# Índices das Point Clouds processadas pelo ti_interpreter
PC_X       = 0
PC_Y       = 1
PC_Z       = 2
PC_DOPPLER = 3
PC_SNR     = 4


def filter_frames(frames, min_doppler=0.05, min_snr=8.0):
    """
    Filtra pontos com ruído em cada frame.

    Filtros aplicados (por ordem):
      1. Doppler  — remove pontos estáticos ou muito lentos:
                      |doppler| > min_doppler  (default 0.05 m/s)
      2. SNR      — remove reflexos fracos (ruído de fundo, paredes distantes):
                      snr > min_snr  (default 8 dB)
    """
    filtered = []
    for arr in frames:
        if arr.shape[0] == 0:
            filtered.append(arr)
        else:
            mask = np.abs(arr[:, PC_DOPPLER]) > min_doppler
            if arr.shape[1] > PC_SNR:
                mask &= arr[:, PC_SNR] > min_snr
            filtered.append(arr[mask])
    return filtered


def filter_by_room_bounds(points, x_min=0.0, x_max=5.5,
                          y_min=0.0, y_max=6.66,
                          z_min=-0.1, z_max=2.5):
    """
    Descarta pontos fora dos limites físicos da sala (pós-conversão para sala).
    """
    if points.shape[0] == 0:
        return points
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    mask = (
        (x >= x_min) & (x <= x_max) &
        (y >= y_min) & (y <= y_max) &
        (z >= z_min) & (z <= z_max)
    )
    return points[mask]


def select_dominant_blob(points_xy, grid_res=0.2, blob_radius=0.8):
    """
    Seleciona apenas os pontos pertencentes ao cluster mais denso num conjunto
    de pontos 2-D (X, Y). Equivalente a um DBSCAN de 1 cluster, sem dependências.
    """
    if points_xy.shape[0] == 0:
        return np.zeros(0, dtype=bool), None

    x = points_xy[:, 0]
    y = points_xy[:, 1]

    x_min, x_max = x.min(), x.max()
    y_min, y_max = y.min(), y.max()

    n_x = max(1, int(np.ceil((x_max - x_min) / grid_res)) + 1)
    n_y = max(1, int(np.ceil((y_max - y_min) / grid_res)) + 1)

    ix = np.clip(((x - x_min) / grid_res).astype(int), 0, n_x - 1)
    iy = np.clip(((y - y_min) / grid_res).astype(int), 0, n_y - 1)

    hist = np.zeros((n_x, n_y), dtype=int)
    np.add.at(hist, (ix, iy), 1)

    peak_ix, peak_iy = np.unravel_index(hist.argmax(), hist.shape)
    cx = x_min + (peak_ix + 0.5) * grid_res
    cy = y_min + (peak_iy + 0.5) * grid_res
    center_xy = np.array([cx, cy])

    dist2 = (x - cx) ** 2 + (y - cy) ** 2
    mask = dist2 <= blob_radius ** 2

    return mask, center_xy
