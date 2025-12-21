FROM caddy:2-builder-alpine AS builder
RUN xcaddy build \
    --with github.com/mholt/caddy-ratelimit \
    --with github.com/porech/caddy-maxmind-geolocation

FROM caddy:2-alpine

# Copy custom-built Caddy binary
COPY --from=builder /usr/bin/caddy /usr/bin/caddy

# Allow binding to privileged ports (80, 443) without root
RUN setcap cap_net_bind_service=ep /usr/bin/caddy

# Create non-root user and set ownership
RUN chown -R 1001:1001 /config /data

# Run as non-root user
USER 1000:1000
