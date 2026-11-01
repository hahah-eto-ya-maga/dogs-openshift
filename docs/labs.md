# Практика: от pod до сети

Сначала выполни `scripts/deploy-openshift.sh`. Команды ниже запускаются из корня репозитория в терминале WSL. Проверь выбранный проект: `oc project dogs-lab` (или своё имя).

## 1. Посмотреть ресурсы

```bash
oc get pods,deploy,rs,sts,svc,route,pvc
oc get builds,bc,is,jobs,cronjobs
oc get configmap,secret,sa,role,rolebinding,networkpolicy,pdb
oc get events --sort-by=.lastTimestamp
oc describe deployment dogs
oc logs deployment/dogs --tail=50
oc logs job/dogs-init
```

`oc get all` показывает не все типы ресурсов. Через `oc describe pod <имя>` посмотри probes, ресурсы, события, образ и монтирования. PV — ресурс уровня кластера; смотреть его может быть запрещено твоей ролью.

## 2. Обойти Route и работать без GUI

```bash
oc port-forward service/dogs 8080:8080
```

Оставь терминал открытым. В другом терминале WSL:

```bash
curl -fsS http://localhost:8080/api/info
curl -fsS http://localhost:8080/api/dogs
```

Или открой `http://localhost:8080` в Windows. Port-forward идёт к выбранному pod, поэтому для проверки балансировки используй Route. Повторные HTTP-запросы через Route могут попадать в один pod из-за sticky sessions — это нормально.

## 3. Самовосстановление и масштабирование

```bash
oc get pods -l app=dogs
oc delete pod <ИМЯ-ОДНОГО-POD-ПРИЛОЖЕНИЯ>
oc get pods -l app=dogs -w
# Ctrl+C останавливает наблюдение, приложение продолжает работать.
oc scale deployment/dogs --replicas=3
oc rollout status deployment/dogs
oc get pods -l app=dogs
oc scale deployment/dogs --replicas=2
```

ReplicaSet создаёт замену удалённому pod. PDB ограничивает добровольное выселение через eviction API, а не прямую команду `oc delete pod`.

## 4. ConfigMap и обновление

```bash
oc patch configmap dogs-config --type=merge \
  -p '{"data":{"WELCOME_MESSAGE":"Привет из WSL!"}}'
oc rollout restart deployment/dogs
oc rollout status deployment/dogs
```

Настройки из environment считываются при создании контейнера. Проверь `/api/info`. Следующий запуск deploy-скрипта применит настройки из YAML; для постоянного изменения редактируй `openshift/base.yaml`.

Измени интерфейс в `app/templates/index.html`, снова запусти deploy-скрипт и посмотри:

```bash
oc rollout history deployment/dogs
oc get builds
# Откат к предыдущему revision, если он существует:
oc rollout undo deployment/dogs
oc rollout status deployment/dogs
```

Скрипт подставляет digest собранного образа, поэтому rollback возвращает предыдущий образ. Изменения ConfigMap и схемы БД rollback Deployment не отменяет.

## 5. Постоянные данные и PostgreSQL

Добавь собаку через браузер или API, затем:

```bash
oc delete pod db-0
oc rollout status statefulset/db --timeout=300s
oc get pvc
oc exec db-0 -- sh -c 'psql -d "$POSTGRESQL_DATABASE" -c "SELECT id,name,status FROM dogs;"'
```

Данные остаются на PVC. Пока единственный PostgreSQL перезапускается, `/readyz` приложения возвращает ошибку и pods временно исключаются из Service. Это учебная БД без репликации и failover.

Резервная копия и восстановление для локального Compose:

```bash
docker compose exec -T db pg_dump -U dogs -d dogs -Fc > dogs.dump
# ВНИМАНИЕ: восстановление заменяет существующие таблицы и данные.
docker compose exec -T db pg_restore -U dogs -d dogs --clean --if-exists < dogs.dump
```

## 6. CronJob и ручной Job

```bash
oc get cronjobs,jobs
oc create job "dogs-report-manual-$(date +%s)" --from=cronjob/dogs-report
oc get jobs
oc logs job/<ИМЯ-СОЗДАННОГО-JOB>
```

Отчёт выводит количество доступных и пристроенных собак. CronJob запускает такой отчёт каждые пять минут. Это отчёт, а не резервная копия.

## 7. RBAC

```bash
oc describe role dogs-observer
oc describe rolebinding dogs-observer
# Следующие проверки требуют прав impersonation, обычно у администратора:
oc auth can-i list pods --as="system:serviceaccount:$(oc project -q):dogs-observer"
oc auth can-i delete pods --as="system:serviceaccount:$(oc project -q):dogs-observer"
```

Ожидается `yes` для list и `no` для delete. Если impersonation запрещён, это ограничение твоих прав, а не ошибка Role. Наблюдатель не получает доступ к Secret.

## 8. NetworkPolicy

```bash
oc describe networkpolicy database-only-from-app
oc describe networkpolicy web-from-router-and-project
```

База принимает TCP 5432 только от pods с метками `app=dogs` или `app=dogs-job` в том же проекте. Приложение принимает HTTP от ingress router и pods текущего проекта. Egress здесь не ограничивается. Сетевые политики требуют поддержки со стороны сетевого плагина кластера.

Проверка запрещённого подключения из pod без разрешённой метки:

```bash
oc run denied-client --image=python:3.12-slim --restart=Never \
  --command -- python -c "import socket; socket.create_connection(('db',5432),timeout=5)"
oc logs -f denied-client
oc delete pod denied-client
```

Ожидается timeout подключения, а не ошибка аутентификации. Для разрешённого подключения повтори с `--labels=app=dogs-job` и другим именем pod; процесс должен завершиться с кодом 0. Эти тесты проверяют только TCP, не пароль БД.

## 9. HPA, квоты и лимиты

```bash
oc apply -f openshift/optional.yaml
oc get hpa
oc adm top pods
oc describe resourcequota dogs-quota
oc describe limitrange dogs-defaults
```

Для HPA нужен API метрик, `requests.cpu` уже задан. При `<unknown>` посмотри `oc describe hpa dogs`. Ручное масштабирование и HPA не используй одновременно: HPA переопределяет replicas. Повторный deploy задаёт replicas=2, после чего HPA снова берёт управление.

Для небольшой нагрузки на учебный стенд (в другом терминале с запущенным port-forward):

```bash
seq 1 2000 | xargs -P 8 -I{} curl -fsS -o /dev/null http://localhost:8080/api/dogs
```

Короткий тест может не вызвать масштабирования: HPA реагирует на усреднённый CPU и использует окна стабилизации. Чтобы убрать дополнительные ограничения:

```bash
oc delete -f openshift/optional.yaml
```

## Если не запускается

| Симптом | Что проверить |
|---|---|
| Docker daemon unavailable | `docker info`, сервис Docker, WSL Integration / systemd |
| Permission denied Docker socket | членство в группе docker, новая сессия |
| PVC Pending | default StorageClass, свободное место, `oc describe pvc data-db-0` |
| Build Failed | `oc logs bc/dogs`, доступ к PyPI/registry, права на Docker builds |
| ImagePullBackOff | события pod, доступ к registry, архитектура образа |
| Job failed | `oc logs job/dogs-init`, пароль, readiness БД, NetworkPolicy |
| Route 503 | `oc get endpoints dogs`, readiness pods, логи приложения |
| Route недоступен при здоровых pods | DNS, сертификат, метки namespace ingress router в NetworkPolicy |
| Forbidden | выбранный проект и разрешения роли |
| CrashLoopBackOff | `oc logs <pod> --previous`, затем `oc describe pod <pod>` |
| Pods Pending после optional.yaml | квота и доступные ресурсы, события pod |

Если в кластере нет default StorageClass, добавь подходящий `storageClassName` в `volumeClaimTemplates` **до первого развёртывания**. Существующий StatefulSet не допускает произвольного изменения шаблона PVC.

## Удаление лаборатории

```bash
# ВНИМАНИЕ: удаляет весь проект, включая его Secret и PVC.
# Делай это только для отдельного проекта этой лаборатории.
oc delete project dogs-lab
```

Удаление PVC обычно приводит к удалению диска, в зависимости от reclaim policy StorageClass. Сначала сохрани нужные данные.
