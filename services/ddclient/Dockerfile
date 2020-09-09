FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update -y && \
    apt upgrade -y && \
    apt install -y --no-install-recommends ddclient \
        libio-socket-ssl-perl \
        libjson-any-perl \
        ca-certificates

COPY entrypoint.sh /
COPY ddclient_raw.conf /

ENV DOMAINS_LIST /domains_list

CMD ["/entrypoint.sh"]
