FROM alpine:3.20

RUN apk add --no-cache kubectl skopeo

COPY refresh-images.sh /usr/local/bin/refresh-images
RUN chmod +x /usr/local/bin/refresh-images

ENTRYPOINT ["/usr/local/bin/refresh-images"]
