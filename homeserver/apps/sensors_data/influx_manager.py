import os
from influxdb_client import InfluxDBClient

def get_influx_client():
    return InfluxDBClient(
        url=os.getenv("INFLUXDB_URL", "http://influxdb:8086"),
        token=os.getenv("INFLUXDB_TOKEN"),
        org=os.getenv("INFLUXDB_ORG")
    )