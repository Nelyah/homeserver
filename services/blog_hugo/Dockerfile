FROM alpine:latest AS builder

RUN apk add --no-cache git hugo

# Fetch the site and build the production static output
RUN git clone --recursive https://github.com/Nelyah/website /website
WORKDIR /website
RUN hugo --environment production --minify --destination /site


FROM alpine:latest

RUN apk add --no-cache python3 uv ca-certificates git openssh-client hugo
WORKDIR /website

# Bring in the built site and source code for the API
COPY --from=builder /website /website
COPY --from=builder /site /website/public

# Install uv and sync dependencies (uses uv.lock when present)
RUN uv sync --all-extras --frozen

RUN git config --system user.email "contact@nelyah.eu" \
    && git config --system user.name "Nelyah"

# Prepare git for SSH pushes; mount keys at runtime
RUN mkdir -p /home/app/.ssh \
    && ssh-keyscan github.com >> /home/app/.ssh/known_hosts \
    && git -C /website remote set-url origin git@github.com:Nelyah/website.git \
    && git config --system --add safe.directory /website

# Create non-root user to match host UID/GID (for mounted SSH key permissions)
ARG APP_UID=1000
ARG APP_GID=1000
RUN addgroup -g ${APP_GID} app || true \
    && adduser -D -u ${APP_UID} -G app app || true \
    && chown -R app:app /website /home/app/.ssh

# Ensure the uv-managed venv is on PATH
ENV VIRTUAL_ENV=/website/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

EXPOSE 1313 8000

# Run as the non-root user (matches mounted key ownership)
USER app

# Serve the static site and the API
CMD ["sh", "-c", "uvicorn api_server:app --host 0.0.0.0 --port 8000 --app-dir /website & python -m http.server 1313 --directory /website/public & wait"]
