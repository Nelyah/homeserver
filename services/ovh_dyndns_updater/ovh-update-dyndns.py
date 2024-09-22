import json
import logging
import os
import ovh
import pydantic
import requests
import sys


logger = logging.getLogger(__name__)


class DynDnsRecord(pydantic.BaseModel):
    id: int
    ip: str
    subDomain: str
    ttl: int
    type: str
    zone: str


def get_public_ipv4() -> str:
    response = requests.get("https://api.ipify.org?format=json")
    return json.loads(response.text)["ip"]


def main():
    application_key = os.getenv("OVH_APPLICATION_KEY")
    application_secret = os.getenv("OVH_APPLICATION_SECRET")
    consumer_key = os.getenv("OVH_CONSUMER_KEY")

    if any([not application_key, not application_secret, not consumer_key]):
        logger.error(
            "Missing environment variables not set: OVH_APPLICATION_KEY",
            " OVH_APPLICATION_SECRET, OVH_CONSUMER_KEY"
        )
        sys.exit(1)

    # Instantiate. Visit https://api.ovh.com/createToken/?GET=/me
    # to get your credentials
    client = ovh.Client(
        endpoint="ovh-eu",
        application_key=application_key,
        application_secret=application_secret,
        consumer_key=consumer_key,
    )

    ipv4 = get_public_ipv4()

    dns_zones: list[str] = client.get("/domain/zone")
    for zone in dns_zones:
        records: list[int] = client.get(f"/domain/zone/{zone}/dynHost/record")

        for record in records:
            # validate json using pydantic
            response_json = client.get(f"/domain/zone/{zone}/dynHost/record/{record}")
            try:
                dynDnsRecord = DynDnsRecord(**response_json)
            except pydantic.ValidationError as e:
                logger.error(f"Error validating json: {e}")
                continue

            if dynDnsRecord.ip != ipv4:
                logger.info(
                    "Updating record"
                    f" {dynDnsRecord.subDomain}.{dynDnsRecord.zone}"
                    f" from {dynDnsRecord.ip} to {ipv4}"
                )
                client.put(f"/domain/zone/{zone}/dynHost/record/{record}", ip=ipv4)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
