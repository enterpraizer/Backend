"""
Synthetic dataset of (project_description → optimal_vm_config) pairs.
Used as few-shot examples in LLM prompts for VM configuration suggestions.
"""
import json

SYNTHETIC_DATASET = [
    # ── Web Applications ──────────────────────────────────────────────────────
    {"description": "Small WordPress blog, <50 visitors/day", "vcpu": 1, "ram_mb": 512, "disk_gb": 10},
    {"description": "Django e-commerce site, ~500 daily users, PostgreSQL backend", "vcpu": 2, "ram_mb": 2048, "disk_gb": 40},
    {"description": "FastAPI REST API, ~1000 requests/min, stateless, Redis cache", "vcpu": 4, "ram_mb": 4096, "disk_gb": 30},
    {"description": "Ruby on Rails app, medium traffic ~5000 users/day, ActiveStorage uploads", "vcpu": 4, "ram_mb": 8192, "disk_gb": 100},
    {"description": "High-traffic Next.js SSR app, ~50k page views/day, CDN in front", "vcpu": 8, "ram_mb": 8192, "disk_gb": 60},
    {"description": "Laravel PHP app with queues, ~200 concurrent users, file uploads", "vcpu": 2, "ram_mb": 4096, "disk_gb": 80},
    {"description": "Static site generator (Hugo/Jekyll) with Nginx, minimal traffic", "vcpu": 1, "ram_mb": 512, "disk_gb": 10},
    {"description": "Django + Celery worker combo, heavy background task processing", "vcpu": 4, "ram_mb": 4096, "disk_gb": 40},
    {"description": "Node.js Express API gateway, high concurrency ~10k req/min", "vcpu": 8, "ram_mb": 8192, "disk_gb": 40},
    {"description": "Flask microservice, internal API only, ~100 req/min", "vcpu": 1, "ram_mb": 1024, "disk_gb": 20},

    # ── Databases ─────────────────────────────────────────────────────────────
    {"description": "PostgreSQL primary node, ~50GB dataset, OLTP workload", "vcpu": 4, "ram_mb": 8192, "disk_gb": 100},
    {"description": "MySQL database for small SaaS, <10GB data, moderate queries", "vcpu": 2, "ram_mb": 4096, "disk_gb": 50},
    {"description": "MongoDB replica set member, document store ~100GB", "vcpu": 4, "ram_mb": 16384, "disk_gb": 200},
    {"description": "Redis cache cluster for high-traffic e-commerce", "vcpu": 2, "ram_mb": 4096, "disk_gb": 20},
    {"description": "Elasticsearch node, full-text search, ~200GB index", "vcpu": 8, "ram_mb": 16384, "disk_gb": 300},
    {"description": "PostgreSQL read replica, reporting queries, ~200GB dataset", "vcpu": 4, "ram_mb": 8192, "disk_gb": 250},
    {"description": "ClickHouse analytics DB, columnar storage, heavy aggregations", "vcpu": 16, "ram_mb": 32768, "disk_gb": 500},
    {"description": "Redis Sentinel for session storage, low data volume", "vcpu": 1, "ram_mb": 2048, "disk_gb": 10},
    {"description": "TimescaleDB for IoT time-series data, ~500k writes/min", "vcpu": 8, "ram_mb": 16384, "disk_gb": 300},
    {"description": "Cassandra node, distributed wide-column store, ~1TB data", "vcpu": 8, "ram_mb": 32768, "disk_gb": 500},

    # ── ML / AI Workloads ─────────────────────────────────────────────────────
    {"description": "ML training pipeline with PyTorch, ImageNet dataset", "vcpu": 8, "ram_mb": 16384, "disk_gb": 200},
    {"description": "Jupyter notebook server for data science, pandas/sklearn", "vcpu": 4, "ram_mb": 8192, "disk_gb": 80},
    {"description": "FastAPI ML inference server, BERT model, ~100 req/min", "vcpu": 4, "ram_mb": 8192, "disk_gb": 40},
    {"description": "LLM fine-tuning job, 7B parameter model, LoRA training", "vcpu": 16, "ram_mb": 65536, "disk_gb": 300},
    {"description": "Airflow worker for ML pipeline orchestration", "vcpu": 4, "ram_mb": 8192, "disk_gb": 60},
    {"description": "Feature store server (Feast), Redis + PostgreSQL backend", "vcpu": 4, "ram_mb": 8192, "disk_gb": 80},
    {"description": "MLflow tracking server, experiment logging, model registry", "vcpu": 2, "ram_mb": 4096, "disk_gb": 100},
    {"description": "YOLOv8 object detection inference API, real-time video frames", "vcpu": 8, "ram_mb": 16384, "disk_gb": 60},
    {"description": "Spark ML job, distributed training on 50GB dataset", "vcpu": 16, "ram_mb": 32768, "disk_gb": 200},
    {"description": "Small NLP text classification API, distilBERT, low traffic", "vcpu": 2, "ram_mb": 4096, "disk_gb": 20},

    # ── CI/CD Runners ─────────────────────────────────────────────────────────
    {"description": "GitHub Actions self-hosted runner, small projects", "vcpu": 2, "ram_mb": 4096, "disk_gb": 40},
    {"description": "Jenkins build agent, Java/Maven projects, Docker builds", "vcpu": 4, "ram_mb": 8192, "disk_gb": 80},
    {"description": "GitLab CI runner, containerized builds, ~10 parallel jobs", "vcpu": 8, "ram_mb": 8192, "disk_gb": 100},
    {"description": "GitHub Actions runner for large monorepo, heavy test suite", "vcpu": 8, "ram_mb": 16384, "disk_gb": 150},
    {"description": "Jenkins master node, orchestrating 20 build agents", "vcpu": 4, "ram_mb": 8192, "disk_gb": 60},
    {"description": "Drone CI runner, lightweight Docker-in-Docker builds", "vcpu": 2, "ram_mb": 2048, "disk_gb": 40},
    {"description": "Tekton pipeline runner on Kubernetes, microservices CI", "vcpu": 4, "ram_mb": 8192, "disk_gb": 60},
    {"description": "ArgoCD application server, GitOps deployments, 30 apps", "vcpu": 2, "ram_mb": 4096, "disk_gb": 20},
    {"description": "SonarQube code quality analysis server, 5 projects", "vcpu": 4, "ram_mb": 8192, "disk_gb": 80},
    {"description": "CircleCI self-hosted runner, Python/Node test suites", "vcpu": 4, "ram_mb": 4096, "disk_gb": 50},

    # ── Game Servers ──────────────────────────────────────────────────────────
    {"description": "Minecraft Java server, ~20 players, vanilla", "vcpu": 2, "ram_mb": 4096, "disk_gb": 20},
    {"description": "Minecraft modded server (ATM9), ~10 players, heavy mods", "vcpu": 4, "ram_mb": 8192, "disk_gb": 40},
    {"description": "CS2 dedicated server, 10v10 competitive, 128-tick", "vcpu": 4, "ram_mb": 4096, "disk_gb": 30},
    {"description": "Valheim dedicated server, ~10 players, world backups", "vcpu": 2, "ram_mb": 4096, "disk_gb": 20},
    {"description": "ARK Survival Evolved server, ~50 players, custom map", "vcpu": 8, "ram_mb": 16384, "disk_gb": 100},
    {"description": "Rust dedicated server, ~100 players, large world", "vcpu": 8, "ram_mb": 16384, "disk_gb": 80},
    {"description": "Terraria multiplayer server, ~10 players, small world", "vcpu": 1, "ram_mb": 1024, "disk_gb": 10},
    {"description": "Factorio headless server, ~5 players, large map", "vcpu": 2, "ram_mb": 2048, "disk_gb": 15},
    {"description": "OpenTTD multiplayer server, ~20 players", "vcpu": 1, "ram_mb": 512, "disk_gb": 10},
    {"description": "Palworld dedicated server, ~32 players, persistent world", "vcpu": 8, "ram_mb": 16384, "disk_gb": 60},

    # ── Microservices ─────────────────────────────────────────────────────────
    {"description": "Auth microservice (JWT), stateless, ~500 req/min", "vcpu": 1, "ram_mb": 512, "disk_gb": 10},
    {"description": "RabbitMQ message broker, 5 queues, moderate throughput", "vcpu": 2, "ram_mb": 2048, "disk_gb": 20},
    {"description": "Kafka broker node, high-throughput event streaming, ~10k msg/s", "vcpu": 4, "ram_mb": 8192, "disk_gb": 100},
    {"description": "API gateway (Kong/Nginx), routing for 15 microservices", "vcpu": 2, "ram_mb": 2048, "disk_gb": 20},
    {"description": "Notification service, email/SMS, Celery workers, low load", "vcpu": 1, "ram_mb": 1024, "disk_gb": 10},
    {"description": "File upload service with S3-compatible storage proxy", "vcpu": 2, "ram_mb": 2048, "disk_gb": 50},
    {"description": "Prometheus + Grafana monitoring stack for 10 services", "vcpu": 2, "ram_mb": 4096, "disk_gb": 50},
    {"description": "gRPC billing microservice, PostgreSQL, ~200 req/min", "vcpu": 2, "ram_mb": 2048, "disk_gb": 20},
    {"description": "WebSocket notification server, ~5000 concurrent connections", "vcpu": 4, "ram_mb": 4096, "disk_gb": 20},
    {"description": "Search microservice wrapping Elasticsearch, ~300 req/min", "vcpu": 2, "ram_mb": 2048, "disk_gb": 15},
]


def main() -> None:
    print(json.dumps(SYNTHETIC_DATASET, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
