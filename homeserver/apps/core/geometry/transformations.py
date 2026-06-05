"""
transformations.py
------------------
Módulo de Álgebra Linear para transformações espaciais 3D.
Isola a matemática pura do resto do sistema.
"""

import numpy as np

def get_rotation_matrix(azimuth_deg: float, tilt_deg: float) -> np.ndarray:
    """
    Gera a matriz de rotação 3x3 baseada nos ângulos de Azimute e Tilt.

    Convenção do projeto:
    - Azimute (phi): Rotação no plano XY (0°=+Y, 90°=+X, 180°=-Y, 270°=-X).
    - Tilt (theta): Inclinação da vertical (0°=chão, 90°=horizontal).
    """
    az_rad   = np.radians(azimuth_deg)
    tilt_rad = np.radians(tilt_deg)

    cos_az = np.cos(az_rad)
    sin_az = np.sin(az_rad)
    cos_t  = np.cos(tilt_rad)
    sin_t  = np.sin(tilt_rad)

    R = np.array([
        [ cos_az,  sin_az * sin_t,  0.0],
        [-sin_az,  cos_az * sin_t,  0.0],
        [    0.0,          -cos_t,  1.0]
    ])

    return R


def transform_radar_to_room(points: np.ndarray, rotation_matrix: np.ndarray, translation: np.ndarray) -> np.ndarray:
    """
    Aplica a transformação linear (Rotação + Translação) a uma nuvem de pontos.

    Parâmetros:
        points: Array numpy (N, >=3) com as coordenadas brutas (x, y, z, ...).
        rotation_matrix: Matriz 3x3 obtida via get_rotation_matrix().
        translation: Vetor (3,) com a posição [x, y, z] do radar na sala.

    Retorna:
        O mesmo array numpy, mas com as 3 primeiras colunas (X, Y, Z)
        transformadas para o referencial da sala. As restantes colunas (Doppler, SNR) são mantidas.
    """
    if points.shape[0] == 0:
        return points.copy()

    xyz = points[:, :3]
    transformed_xyz = (xyz @ rotation_matrix.T) + translation

    out = points.copy().astype(float)
    out[:, :3] = transformed_xyz

    return out
