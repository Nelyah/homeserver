import json
import logging
import os
import ovh
import pydantic
import requests
import signal
import sys
import time


logger = logging.getLogger(__name__)


class DynDnsRecord(pydantic.BaseModel):
    id: int
    ip: str
    subDomain: str
    ttl: int
    type: str
    zone: str


def get_public_ipv4() -> str:
    response = requests.get("https://api.ipify.org?format=json", timeout=10)
    response.raise_for_status()
    return response.json()["ip"]


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def parse_interval_seconds() -> int:
    raw = os.getenv("INTERVAL_SECONDS", "600")
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid INTERVAL_SECONDS={raw!r}, must be an integer") from exc
    if value < 30:
        raise RuntimeError("INTERVAL_SECONDS must be >= 30")
    return value


def run_once(client: ovh.Client) -> None:
    ipv4 = get_public_ipv4()
    logger.info("Current public IPv4: %s", ipv4)

    dns_zones: list[str] = client.get("/domain/zone")
    for zone in dns_zones:
        records: list[int] = client.get(f"/domain/zone/{zone}/dynHost/record")
        for record in records:
            response_json = client.get(f"/domain/zone/{zone}/dynHost/record/{record}")
            try:
                dyn_dns_record = DynDnsRecord(**response_json)
            except pydantic.ValidationError as exc:
                logger.error("Error validating OVH response JSON: %s", exc)
                continue

            if dyn_dns_record.ip == ipv4:
                continue

            logger.info(
                "Updating record %s.%s from %s to %s",
                dyn_dns_record.subDomain,
                dyn_dns_record.zone,
                dyn_dns_record.ip,
                ipv4,
            )
            client.put(f"/domain/zone/{zone}/dynHost/record/{record}", ip=ipv4)


def main() -> None:
    application_key = os.getenv("OVH_APPLICATION_KEY")
    application_secret = os.getenv("OVH_APPLICATION_SECRET")
    consumer_key = os.getenv("OVH_CONSUMER_KEY")

    if any([not application_key, not application_secret, not consumer_key]):
        raise RuntimeError(
            "Missing one or more required environment variables: "
            "OVH_APPLICATION_KEY, OVH_APPLICATION_SECRET, OVH_CONSUMER_KEY"
        )

    # Instantiate. Visit https://api.ovh.com/createToken/?GET=/me
    # to get your credentials
    client = ovh.Client(
        endpoint="ovh-eu",
        application_key=require_env("OVH_APPLICATION_KEY"),
        application_secret=require_env("OVH_APPLICATION_SECRET"),
        consumer_key=require_env("OVH_CONSUMER_KEY"),
    )

    interval_seconds = parse_interval_seconds()
    logger.info("Starting OVH DynDNS updater loop (interval=%ss)", interval_seconds)

    stop = False

    def handle_signal(signum, _frame):
        nonlocal stop
        logger.info("Received signal %s, shutting down", signum)
        stop = True

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    while not stop:
        try:
            run_once(client)
        except Exception:
            logger.exception("OVH DynDNS updater iteration failed")

        slept = 0
        while not stop and slept < interval_seconds:
            time.sleep(min(1, interval_seconds - slept))
            slept += 1


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
    try:
        main()
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)
