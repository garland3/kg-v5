#!/bin/bash
set -e

# Set correct permissions for pgpass file
chmod 600 /pgpass

# Call the original entrypoint
exec /entrypoint.sh "$@"
