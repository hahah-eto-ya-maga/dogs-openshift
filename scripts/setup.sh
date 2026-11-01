#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f .env ]]; then
  umask 077
  printf 'DB_PASSWORD=%s\nAPP_PORT=8080\n' "$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')" > .env
  echo 'Создан .env со случайным паролем.'
fi
docker compose version >/dev/null
docker info >/dev/null
docker compose up --build -d --wait --wait-timeout 180
echo 'Готово: http://localhost:8080 (открой в браузере Windows или используй curl)'
