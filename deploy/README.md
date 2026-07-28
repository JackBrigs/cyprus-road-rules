# Деплой

```
deploy/
└── k8s/
    ├── base/                     # то, что одинаково в любом окружении
    │   ├── kustomization.yaml
    │   ├── namespace.yaml
    │   ├── deployment.yaml
    │   ├── pvc.yaml
    │   └── secret.example.yaml   # шаблон, в kustomization не подключён
    └── overlays/
        └── production/           # реестр, тег образа и ресурсы
            ├── kustomization.yaml
            └── patch-resources.yaml
```

`Dockerfile` и `docker-compose.yml` лежат в корне репозитория: контекст сборки —
корень, а `docker compose up` привычнее находить именно там.

## Сборка образа

Изображения знаков запекаются в образ, поэтому **шаг 0 из основного README нужно
выполнить до сборки** — иначе `assets/` окажется пустым.

```bash
docker build -t ghcr.io/jackbrigs/cyprus-road-rules:v0.1.0 .
docker push ghcr.io/jackbrigs/cyprus-road-rules:v0.1.0
```

Проверить образ локально:

```bash
docker run --rm --read-only --tmpfs /tmp \
  -v bot-data:/app/var \
  -e BOT_TOKEN='<токен>' -e DB_PATH=/app/var/bot.db \
  ghcr.io/jackbrigs/cyprus-road-rules:v0.1.0
```

## Kubernetes

Секрет с токеном в репозитории не хранится — создайте его в кластере:

```bash
kubectl create namespace cyprus-signs-bot
kubectl -n cyprus-signs-bot create secret generic bot-secrets \
  --from-literal=BOT_TOKEN='<токен от @BotFather>'
```

Посмотреть, что получится, и применить:

```bash
kubectl kustomize deploy/k8s/overlays/production      # рендер без применения
kubectl apply -k deploy/k8s/overlays/production
kubectl -n cyprus-signs-bot logs -f deploy/cyprus-signs-bot
```

Разворачивать нужно **оверлей**, а не `base`: в базе образ оставлен
плейсхолдером `cyprus-signs-bot` без реестра и тега.

## Решения, которые стоит понимать

**Одна реплика и стратегия `Recreate`.** Бот работает в режиме long polling: два
пода начали бы разбирать одни и те же апдейты, и Telegram отдавал бы их
попеременно то одному, то другому — пользователь видел бы пропадающие ответы.
При `RollingUpdate` новый под поднимался бы до остановки старого и получил бы
ровно эту ситуацию, плюс не смог бы примонтировать RWO-том. Масштабировать этот
Deployment нельзя — при необходимости горизонтального роста нужен webhook-режим
и внешняя БД вместо SQLite.

**Нет Service и Ingress.** Входящих соединений у бота нет, он сам ходит в
Telegram. Открывать порт нечему.

**Нет проб.** Бот не слушает порт, HTTP-пробы не к чему прицепить. Падение
процесса — это выход контейнера, его перезапустит kubelet.

**PVC на 1 ГиБ, ReadWriteOnce.** В SQLite лежат прогресс пользователей, кэш
`file_id` и состояние сессий. Объём крошечный, но том обязателен: без него
перезапуск пода стёр бы весь прогресс.

**Состояние переживает перезапуск.** FSM-состояние теста хранится в той же
SQLite, поэтому rollout не обрывает начатый пользователем тест.
