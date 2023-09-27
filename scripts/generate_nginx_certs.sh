#!/bin/bash

check_expiry() {
  local cert=$1
  local expiration_date=$(openssl x509 -in $cert -noout -enddate 2>/dev/null | cut -d= -f2)
  
  if [ -z "$expiration_date" ]; then
    return 1
  fi

  local expiration_seconds=$(date -d "$expiration_date" +%s)
  local current_seconds=$(date +%s)

  if [ $current_seconds -ge $expiration_seconds ]; then
    return 1
  fi

  return 0
}

generate_cert() {
  local key=$1
  local cert=$2
  local subj=$3

  if ! check_expiry $cert; then
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout $key -out $cert -subj $subj
  fi
}


generate_cert "/certs/localhost.key" "/certs/localhost.crt" "/CN=localhost"
generate_cert "/certs/key.pem" "/certs/cert.pem" "/CN=localhost"

exec /opt/bitnami/scripts/nginx/run.sh
