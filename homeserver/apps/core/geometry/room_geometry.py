"""
core/geometry/room_geometry.py
------------------------------
Conversão espacial de coordenadas radar → sala.
Partilhado entre o SpatialAligner e a fusão visual do dashboard.
"""

import numpy as np
from core.geometry.transformations import get_rotation_matrix, transform_radar_to_room


def radar_to_room(points_array: np.ndarray, radar_cfg: dict) -> np.ndarray:
    """
    Transforma pontos do referencial local do radar para o referencial da sala.

    Parâmetros
    ----------
    points_array : np.ndarray (N, >=3)  — coordenadas brutas [x, y, z, ...]
    radar_cfg    : dict — configuração do radar com as chaves:
                     'position_m': {'x': float, 'y': float, 'z': float}
                     'azimuth_deg': float
                     'tilt_deg'   : float

    Retorna
    -------
    np.ndarray (N, >=3) com XYZ transformados; colunas extra (Doppler, SNR) mantidas.
    """
    if points_array.shape[0] == 0:
        return points_array.copy()

    pos = radar_cfg["position_m"]
    translation     = np.array([pos["x"], pos["y"], pos["z"]])
    rotation_matrix = get_rotation_matrix(
        radar_cfg.get("azimuth_deg", 0.0),
        radar_cfg.get("tilt_deg", 0.0),
    )
    return transform_radar_to_room(points_array, rotation_matrix, translation)
