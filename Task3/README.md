# Task3.1 Минимальный прототип OpenTelemetry/Jaeger

В этой папке находится минимальный прототип распределенной трассировки для задания 3.1. Он показывает, как входящий HTTP-запрос в `service-a` порождает вызов нижестоящего сервиса `service-b`, а Jaeger собирает оба участка обработки в один трейс.

## Состав артефактов

- `services/service-a` - Python Flask-сервис, который принимает заказ на `/`, создает `order_id`, добавляет атрибуты заказа в текущий спан и вызывает `service-b`.
- `services/service-b` - Python Flask-сервис, который обрабатывает `/manufacturing-plan`, добавляет производственные атрибуты в текущий спан и возвращает JSON с планом производства.
- `k8s/services.yaml` - Kubernetes-манифесты для развертывания `service-a` и `service-b`.
- `k8s/jaeger-instance.yaml` - минимальный экземпляр Jaeger для Jaeger Operator.
- `screenshots/jaeger-trace.png` - скриншот из Jaeger UI с трейсом, где видны спаны обоих сервисов.

## Что реализовано

- Оба сервиса отправляют трейсы через OTLP HTTP exporter в Jaeger.
- `service-a` инструментирован для входящих Flask-запросов и исходящих HTTP-вызовов через `requests`.
- `service-b` инструментирован для входящих Flask-запросов.
- Контекст трассировки передается из `service-a` в `service-b` автоматически через OpenTelemetry-инструментацию HTTP-клиента и сервера.
- В спаны добавлены доменные атрибуты: `order.id`, `order.system`, `downstream.service`, `downstream.status_code`, `manufacturing.plan_id`, `manufacturing.line`, `manufacturing.priority`.
- Оба сервиса открывают `/health` для проверок готовности и живости.

## Проверочный сценарий

Основной сценарий проверки:

1. Развернуть Jaeger, `service-a` и `service-b`.
2. Выполнить HTTP-вызов в `service-a`.
3. Открыть Jaeger UI.
4. Найти последний трейс сервиса `service-a`.
5. Проверить, что один трейс содержит спаны `service-a` и `service-b`.

Ожидаемый ответ `service-a` содержит статус вызова `service-b` и план производства:

```json
{
  "downstream_status": 200,
  "manufacturing_plan": {
    "line": "alexandrite-line-1",
    "status": "planned"
  },
  "order_id": "<uuid>"
}
```

Подтверждение выполненной проверки находится в `screenshots/jaeger-trace.png`.

## Воспроизведение в Minikube

Собрать локальные образы внутри Minikube:

```bash
minikube start
minikube image build -t alexandrite/service-a:local Task3/services/service-a
minikube image build -t alexandrite/service-b:local Task3/services/service-b
```

Установить зависимости для Jaeger Operator и применить экземпляр Jaeger:

```bash
kubectl create namespace observability --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.5/cert-manager.yaml
kubectl wait --for=condition=Available deployment/cert-manager -n cert-manager --timeout=180s
kubectl wait --for=condition=Available deployment/cert-manager-cainjector -n cert-manager --timeout=180s
kubectl wait --for=condition=Available deployment/cert-manager-webhook -n cert-manager --timeout=180s
for i in $(seq 1 120); do
  ca_bundle_bytes=$(kubectl get validatingwebhookconfiguration cert-manager-webhook -o jsonpath='{.webhooks[0].clientConfig.caBundle}' | wc -c | tr -d ' ')
  if [ "$ca_bundle_bytes" -gt 0 ]; then
    break
  fi
  sleep 1
done
test "$ca_bundle_bytes" -gt 0
curl -L https://github.com/jaegertracing/jaeger-operator/releases/download/v1.57.0/jaeger-operator.yaml \
  | sed 's#gcr.io/kubebuilder/kube-rbac-proxy:v0.13.1#quay.io/brancz/kube-rbac-proxy:v0.13.1#g' \
  | kubectl apply -n observability -f -
kubectl rollout status deployment/jaeger-operator -n observability
kubectl apply -f Task3/k8s/jaeger-instance.yaml
for i in $(seq 1 120); do
  kubectl get deployment/simplest >/dev/null 2>&1 && break
  sleep 1
done
kubectl rollout status deployment/simplest --timeout=180s
for i in $(seq 1 120); do
  kubectl get service/simplest-query >/dev/null 2>&1 && break
  sleep 1
done
kubectl get service/simplest-query
```

Если Jaeger Operator уже установлен, достаточно применить `Task3/k8s/jaeger-instance.yaml`.

Развернуть сервисы:

```bash
kubectl apply -f Task3/k8s/services.yaml
kubectl rollout status deployment/service-b
kubectl rollout status deployment/service-a
```

Вызвать `service-a` из запущенного пода:

```bash
kubectl exec -it $(kubectl get pods -l app=service-a -o jsonpath='{.items[0].metadata.name}') -- wget -qO- http://service-a:8080
```

Открыть Jaeger UI:

```bash
kubectl port-forward service/simplest-query 16686:16686
```

После этого Jaeger UI доступен по адресу `http://localhost:16686`.
