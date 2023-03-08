from prometheus_client import Gauge, Enum, generate_latest, CONTENT_TYPE_LATEST
from dataclasses import dataclass
import os
import subprocess
import json
from fastapi import FastAPI
from fastapi.responses import Response

import logging
import sys

date_strftime_format = "%d-%b-%y %H:%M:%S"
message_format = "%(asctime)s - %(levelname)s - %(message)s"

logging.basicConfig(
    format=message_format,
    level=logging.INFO,
    datefmt=date_strftime_format,
    stream=sys.stdout,
)


@dataclass
class SmartcltExporter:
    labels: list[str]
    raw_read_error_rate: Gauge = Gauge(
        "smartctl_raw_read_error_rate", "Raw Read Error Rate", ["device"]
    )
    spin_up_time: Gauge = Gauge(
        "smartctl_spin_up_time", "Spin up time", ["device"])
    start_stop_count: Gauge = Gauge(
        "smartctl_start_stop_count",
        "Number of time disk has been started and stopped",
        ["device"],
    )
    reallocated_sector_count: Gauge = Gauge(
        "smartctl_reallocated_sector_count", "Reallocated sectors", ["device"]
    )
    seek_error_rate: Gauge = Gauge(
        "smartctl_seek_error_rate", "Rate of seek error", ["device"]
    )
    power_on_hours: Gauge = Gauge(
        "smartctl_power_on_hours", "Number of powered on hours", ["device"]
    )
    spin_retry_count: Gauge = Gauge(
        "smartctl_spin_retry_count", "Number of Spin retry", ["device"]
    )
    calibration_retry_count: Gauge = Gauge(
        "smartctl_calibration_retry_count", "Calibrated retries", ["device"]
    )
    power_cycle_count: Gauge = Gauge(
        "smartctl_power_cycle_count", "Number of power cycles", ["device"]
    )
    power_off_retract_count: Gauge = Gauge(
        "smartctl_power_off_retract_count", "Number of power off retracts", [
            "device"]
    )
    load_cycle_count: Gauge = Gauge(
        "smartctl_load_cycle_count", "Number of load cycle", ["device"]
    )
    temperature_celsius: Gauge = Gauge(
        "smartctl_temperature_celsius", "Temperature", ["device"]
    )
    reallocated_event_count: Gauge = Gauge(
        "smartctl_reallocated_event_count", "Number of reallocated events", [
            "device"]
    )
    current_pending_sector: Gauge = Gauge(
        "smartctl_current_pending_sector",
        "Number of currently pending sectors",
        ["device"],
    )
    offline_uncorrectable: Gauge = Gauge(
        "smartctl_offline_uncorrectable", "Offline uncorrectable", ["device"]
    )
    udma_crc_error_count: Gauge = Gauge(
        "smartctl_udma_crc_error_count", "Number of UDMA crc errors", [
            "device"]
    )
    multi_zone_error_rate: Gauge = Gauge(
        "smartctl_multi_zone_error_rate", "Rate of multi zone errors", [
            "device"]
    )
    short_self_test_state: Enum = Enum(
        "smartctl_short_self_test_state",
        "State of the short self tests",
        ["device"],
        states=["passing", "failing"],
    )

    def _collect_device_data(self, label: str) -> None:
        """Collect SMART data for one specific device"""
        job = subprocess.run(
            ["/usr/bin/env", "smartctl", "--json", "-a", label],
            check=False,
            capture_output=True,
        )

        try:
            data = json.loads(job.stdout)
        except json.decoder.JSONDecodeError:
            return
        if (
            "ata_smart_self_test_log" in data
            and "table" in data["ata_smart_self_test_log"]["standard"]
        ):
            for test_log in data["ata_smart_self_test_log"]["standard"]["table"]:
                if test_log["type"]["value"] == 1:
                    self.short_self_test_state.labels(device=label).state(
                        "passing" if test_log["status"]["passed"] else "failing",
                    )

        if "ata_smart_attributes" in data and "table" in data["ata_smart_attributes"]:
            for smart_attribute in data["ata_smart_attributes"]["table"]:
                attr_name = (
                    smart_attribute["name"]
                    .lower()
                    .replace("-", "_")
                    .replace("_ct", "_count")
                )

                if attr_name in self.__dict__:
                    self.__getattribute__(attr_name).labels(device=label).set(
                        smart_attribute["raw"]["value"],
                    )

    def collect_data(self) -> None:
        """Collect data for all the available devices"""
        for label in self.labels:
            self._collect_device_data(label)


app = FastAPI()


def get_smart_devices() -> list[str]:
    """Get the devices to read the data from

    Each value should be separated my colons, ex:
    /dev/sda:/dev/sdb:/dev/sdc
    """
    device_list = os.getenv("SMART_DEVICES")
    if device_list is None:
        return []

    return device_list.split(":")


@app.middleware("http")
async def get_all_metrics(request, call_next):
    logging.info(
        f"Getting SMART data metrics for {', '.join(get_smart_devices())}")
    exporter = SmartcltExporter(get_smart_devices())
    exporter.collect_data()
    response = await call_next(request)
    return response


@app.get("/metrics")
async def return_metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
