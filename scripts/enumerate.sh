#!/usr/bin/env bash
# Passive subdomain enumeration for one domain.
# Usage: enumerate.sh <domain>   (prints hostnames to stdout, one per line)
set -uo pipefail
domain="$1"

{
  subfinder -d "$domain" -all -silent 2>/dev/null
  assetfinder --subs-only "$domain" 2>/dev/null
  curl -s --max-time 60 "https://crt.sh/?q=%25.${domain}&output=json" \
    | jq -r '.[].name_value' 2>/dev/null | tr ';' '\n' | sed 's/\*\.//g'
} | tr 'A-Z' 'a-z' | grep -E "(^|\.)${domain//./\\.}$" | sort -u
