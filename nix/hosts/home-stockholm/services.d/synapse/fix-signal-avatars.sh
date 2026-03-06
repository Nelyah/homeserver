#!/usr/bin/env bash
# Fix Signal DM room avatars by copying member avatars to rooms
# Run this from the homeserver where docker is available

set -euo pipefail

# Configuration
SYNAPSE_CONTAINER="${SYNAPSE_CONTAINER:-synapse}"
DB_CONTAINER="${DB_CONTAINER:-synapse_db}"
DB_USER="${DB_USER:-synapse}"
DB_NAME="${DB_NAME:-synapse}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== Signal Room Avatar Fixer ==="
echo ""

# Check if token is provided
if [ -z "${MATRIX_TOKEN:-}" ]; then
    echo -e "${RED}Error: MATRIX_TOKEN environment variable is required${NC}"
    echo ""
    echo "Usage: MATRIX_TOKEN=syt_xxx $0"
    echo ""
    echo "Get a token from the database:"
    echo "  docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c \\"
    echo "    \"SELECT token FROM access_tokens WHERE user_id = '@nelyah:nelyah.eu' AND valid_until_ms IS NULL ORDER BY id DESC LIMIT 1;\""
    exit 1
fi

# Check containers are running
if ! docker ps --format '{{.Names}}' | grep -q "^${SYNAPSE_CONTAINER}$"; then
    echo -e "${RED}Error: Synapse container '$SYNAPSE_CONTAINER' is not running${NC}"
    exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    echo -e "${RED}Error: Database container '$DB_CONTAINER' is not running${NC}"
    exit 1
fi

# Get all Signal DM rooms missing avatar but where contact has avatar
echo "Querying database for Signal rooms without avatars..."

QUERY="
SELECT DISTINCT ON (r.room_id)
    r.room_id,
    p.avatar_url,
    p.displayname
FROM rooms r
JOIN room_memberships rm ON r.room_id = rm.room_id
JOIN profiles p ON rm.user_id = p.full_user_id
WHERE r.creator = '@signalbot:nelyah.eu'
  AND p.full_user_id LIKE '@signal_%'
  AND p.full_user_id != '@signalbot:nelyah.eu'
  AND p.avatar_url IS NOT NULL
  AND p.avatar_url != ''
  -- Only DM rooms (exactly 3 members: you, contact, signalbot)
  AND (
    SELECT COUNT(*) FROM current_state_events cse_count
    JOIN event_json e_count ON cse_count.event_id = e_count.event_id
    WHERE cse_count.room_id = r.room_id
    AND cse_count.type = 'm.room.member'
    AND json_extract_path_text(e_count.json::json, 'content', 'membership') = 'join'
  ) = 3
  -- Room has no avatar set
  AND NOT EXISTS (
    SELECT 1 FROM current_state_events cse
    WHERE cse.room_id = r.room_id AND cse.type = 'm.room.avatar'
  )
  -- User is a member
  AND EXISTS (
    SELECT 1 FROM current_state_events cse2
    JOIN event_json e ON cse2.event_id = e.event_id
    WHERE cse2.room_id = r.room_id
    AND cse2.type = 'm.room.member'
    AND cse2.state_key = '@nelyah:nelyah.eu'
    AND json_extract_path_text(e.json::json, 'content', 'membership') = 'join'
  )
ORDER BY r.room_id, p.displayname;
"

ROOMS=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -A -c "$QUERY")

if [ -z "$ROOMS" ]; then
    echo -e "${GREEN}No Signal rooms need avatar fixes!${NC}"
    exit 0
fi

TOTAL=$(echo "$ROOMS" | wc -l)
echo "Found $TOTAL Signal rooms to fix"
echo ""

# Process each room
COUNT=0
SUCCESS=0
FAILED=0

while IFS='|' read -r ROOM_ID AVATAR_URL DISPLAYNAME; do
    if [ -n "$ROOM_ID" ] && [ -n "$AVATAR_URL" ]; then
        COUNT=$((COUNT + 1))

        # URL encode the room ID
        ENCODED_ROOM_ID=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$ROOM_ID', safe=''))")

        printf "[%d/%d] %-30s ... " "$COUNT" "$TOTAL" "$DISPLAYNAME"

        RESULT=$(docker exec "$SYNAPSE_CONTAINER" curl -s -X PUT \
            "https://matrix.nelyah.eu/_matrix/client/v3/rooms/${ENCODED_ROOM_ID}/state/m.room.avatar" \
            -H "Authorization: Bearer $MATRIX_TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"url\": \"$AVATAR_URL\"}" 2>&1)

        if echo "$RESULT" | grep -q "event_id"; then
            echo -e "${GREEN}OK${NC}"
            SUCCESS=$((SUCCESS + 1))
        else
            echo -e "${RED}FAILED${NC}"
            echo "  Error: $RESULT"
            FAILED=$((FAILED + 1))
        fi
    fi
done <<< "$ROOMS"

echo ""
echo "=== Summary ==="
echo -e "Total processed: $COUNT"
echo -e "Successful: ${GREEN}$SUCCESS${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
