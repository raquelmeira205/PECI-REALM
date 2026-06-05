from influxdb_client import InfluxDBClient
from django.conf import settings
import numpy as np
from collections import defaultdict


def get_radar_calibration_snapshot(radar_sn, seconds=10, start_time=None, stop_time=None):
    """
    Busca pontos no InfluxDB para a calibração visual.
    Se start_time e stop_time (datetime UTC) forem fornecidos, usa janela absoluta.
    Caso contrário usa os últimos N segundos.
    Devolve lista de [x, y, z]. Em caso de erro de ligação devolve [].
    """
    if not settings.INFLUXDB_TOKEN:
        return []

    try:
        client = InfluxDBClient(
            url=settings.INFLUXDB_URL,
            token=settings.INFLUXDB_TOKEN,
            org=settings.INFLUXDB_ORG,
        )
        query_api = client.query_api()

        if start_time and stop_time:
            range_clause = (
                f'range(start: {start_time.strftime("%Y-%m-%dT%H:%M:%SZ")}, '
                f'stop: {stop_time.strftime("%Y-%m-%dT%H:%M:%SZ")})'
            )
        else:
            range_clause = f'range(start: -{seconds}s)'

        query = f'''
            from(bucket: "{settings.INFLUXDB_BUCKET}")
            |> {range_clause}
            |> filter(fn: (r) => r["_measurement"] == "radar_data")
            |> filter(fn: (r) => r["radar_sn"] == "{radar_sn}")
            |> pivot(rowKey:["_time", "target_id"], columnKey: ["_field"], valueColumn: "_value")
        '''

        result = query_api.query(org=settings.INFLUXDB_ORG, query=query)
        points = []

        for table in result:
            for record in table.records:
                points.append([record["x"], record["y"], record["z"]])

        return points

    except Exception:
        return []
    finally:
        try:
            client.close()
        except Exception:
            pass


def get_radar_pointcloud_snapshot(radar_sn, seconds=10, start_time=None, stop_time=None):
    """
    Busca pontos raw (measurement radar_raw_pc) no InfluxDB.
    Devolve lista de [x, y, z]. Em caso de erro devolve [].
    """
    if not settings.INFLUXDB_TOKEN:
        return []
    try:
        client = InfluxDBClient(
            url=settings.INFLUXDB_URL,
            token=settings.INFLUXDB_TOKEN,
            org=settings.INFLUXDB_ORG,
        )
        query_api = client.query_api()
        if start_time and stop_time:
            range_clause = (
                f'range(start: {start_time.strftime("%Y-%m-%dT%H:%M:%SZ")}, '
                f'stop: {stop_time.strftime("%Y-%m-%dT%H:%M:%SZ")})'
            )
        else:
            range_clause = f'range(start: -{seconds}s)'
        query = f'''
            from(bucket: "{settings.INFLUXDB_BUCKET}")
            |> {range_clause}
            |> filter(fn: (r) => r["_measurement"] == "radar_raw_pc")
            |> filter(fn: (r) => r["radar_sn"] == "{radar_sn}")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        result = query_api.query(org=settings.INFLUXDB_ORG, query=query)
        points = []
        for table in result:
            for record in table.records:
                points.append([record["x"], record["y"], record["z"]])
        return points
    except Exception:
        return []
    finally:
        try:
            client.close()
        except Exception:
            pass


def get_radar_frames_for_alignment(radar_sn, start_time, stop_time):
    """
    Consulta o measurement 'radar_raw_pc' no InfluxDB e devolve uma lista de frames
    compatível com SpatialAligner._build_windows().

    Cada frame é um dict:
      'pointCloud'            : np.ndarray (N, 5)  — [x, y, z, doppler, snr]
      'absolute_timestamp_sec': float

    Retorna [] se não houver dados ou se a ligação falhar.
    """
    if not settings.INFLUXDB_TOKEN:
        return []

    try:
        client = InfluxDBClient(
            url=settings.INFLUXDB_URL,
            token=settings.INFLUXDB_TOKEN,
            org=settings.INFLUXDB_ORG,
        )
        query_api = client.query_api()

        range_clause = (
            f'range(start: {start_time.strftime("%Y-%m-%dT%H:%M:%SZ")}, '
            f'stop: {stop_time.strftime("%Y-%m-%dT%H:%M:%SZ")})'
        )

        query = f'''
            from(bucket: "{settings.INFLUXDB_BUCKET}")
            |> {range_clause}
            |> filter(fn: (r) => r["_measurement"] == "radar_raw_pc")
            |> filter(fn: (r) => r["radar_sn"] == "{radar_sn}")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''

        result = query_api.query(org=settings.INFLUXDB_ORG, query=query)

        # Agrupa pontos por timestamp — cada timestamp distinto = uma frame
        frames_by_ts = defaultdict(list)
        for table in result:
            for record in table.records:
                ts = record.get_time()
                ts_sec = ts.timestamp() if ts else None
                pt = [
                    record.values.get("x",       0.0),
                    record.values.get("y",       0.0),
                    record.values.get("z",       0.0),
                    record.values.get("doppler", 0.0),
                    record.values.get("snr",     0.0),
                ]
                frames_by_ts[ts_sec].append(pt)

        frames = []
        for ts_sec in sorted(frames_by_ts.keys()):
            frames.append({
                "pointCloud":             np.array(frames_by_ts[ts_sec], dtype=float),
                "absolute_timestamp_sec": ts_sec,
            })

        return frames

    except Exception:
        return []
    finally:
        try:
            client.close()
        except Exception:
            pass
