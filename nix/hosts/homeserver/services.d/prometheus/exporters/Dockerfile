FROM python
MAINTAINER Chloé Dequeker <contact@nelyah.eu>

USER root

RUN apt-get update && apt-get install -y smartmontools && rm -rf /var/lib/apt/lists/*

WORKDIR /exporter
COPY ./requirements.txt /exporter/requirements.txt
RUN pip3 install -r requirements.txt

COPY ./smartctl_exporter.py /exporter/smartctl_exporter.py

SHELL ["/bin/bash", "-l", "-c"]
# ENTRYPOINT ["/bin/bash", "-l"]
ENTRYPOINT ["/usr/bin/env", "uvicorn", "--host", "0.0.0.0" ,"smartctl_exporter:app"]

