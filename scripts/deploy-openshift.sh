#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT="${PROJECT:-dogs-lab}"
[[ "$PROJECT" =~ ^[a-z][a-z0-9-]*$ ]] || { echo 'Недопустимое имя проекта'; exit 1; }
oc whoami >/dev/null
if ! oc get project "$PROJECT" >/dev/null 2>&1; then oc new-project "$PROJECT"; fi
oc project "$PROJECT"
if ! oc get secret dogs-secret >/dev/null 2>&1; then
  secret_file=$(mktemp)
  trap 'rm -f "$secret_file"' EXIT
  chmod 600 "$secret_file"
  printf 'DB_PASSWORD=%s\n' "$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')" > "$secret_file"
  oc create secret generic dogs-secret --from-env-file="$secret_file"
  rm -f "$secret_file"
  trap - EXIT
fi
oc apply -f openshift/build.yaml
# Send only build inputs: .env and Git credentials never enter the build archive.
build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT
cp Dockerfile requirements.txt .dockerignore "$build_dir/"
cp -R app "$build_dir/"
oc start-build dogs --from-dir="$build_dir" --follow --wait
rm -rf "$build_dir"
trap - EXIT
IMAGE=$(oc get istag dogs:latest -o jsonpath='{.image.dockerImageReference}')
[[ -n "$IMAGE" ]] || { echo 'Образ не найден'; exit 1; }
oc apply -f openshift/base.yaml
oc apply -f openshift/network.yaml
oc rollout status statefulset/db --timeout=300s
oc delete job dogs-init --ignore-not-found --wait=true
sed "s|DOGS_IMAGE|$IMAGE|g" openshift/jobs.yaml | oc apply -f -
if ! oc wait --for=condition=complete job/dogs-init --timeout=300s; then
  oc logs job/dogs-init --all-containers=true
  exit 1
fi
sed "s|DOGS_IMAGE|$IMAGE|g" openshift/app.yaml | oc apply -f -
oc rollout status deployment/dogs --timeout=300s
printf 'Готово: https://%s\n' "$(oc get route dogs -o jsonpath='{.spec.host}')"
