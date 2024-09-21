#! /bin/bash
for container_id in $(journalctl --since '1 hour ago' -u docker | \
                        grep "Error streaming logs.*invalid character" | \
                        sed -r 's/^.*container=([^ ]+) .*/\1/' | \
                        sort -u); do

    echo >&2 "Truncating corrupted logs for container $container_id"
    truncate -s0 "$(docker container inspect --format='{{.LogPath}}' "$container_id")"
done
