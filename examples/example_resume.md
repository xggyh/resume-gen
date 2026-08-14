# Alex Chen
Senior Software Engineer · Backend & ML Systems
alex.chen@example.com · +1 (415) 555-0142 · San Francisco, CA
linkedin.com/in/alexchen · github.com/alexchen

## Summary
Backend engineer with 7 years of experience building distributed data and ML systems. Comfortable owning systems end-to-end, from prototype to production.

## Work Experience

### Senior Software Engineer, Skyline Analytics — San Francisco, CA
2022-03 – Present
- Led the redesign of the realtime feature platform serving 1.2B events/day for fraud and risk models; cut p99 lookup latency from 180ms to 42ms by introducing tiered Redis/Aerospike caching.
- Designed and shipped a Kafka-based change-data-capture pipeline (Debezium + Flink) connecting 30+ Postgres tables to the lakehouse; reduced data freshness from hours to under 90 seconds.
- Built a Python SDK and self-serve config layer that let 20+ data scientists deploy new features without engineering involvement; feature deploys per week increased 4x.
- Owned the migration of the model serving stack from custom Flask containers to KServe on Kubernetes; cut infra cost 28% and improved cold start by 6x.
- Mentored 3 mid-level engineers, ran weekly system design office hours, and led the migration roadmap presented to the VP of Engineering.

### Software Engineer, Quantum Logistics — Seattle, WA
2019-06 – 2022-02
- Implemented the route-optimization microservice (Go) handling 80k requests/min, with custom heuristic + OR-Tools fallback; improved on-time delivery rate by 11 percentage points.
- Rebuilt observability stack on top of OpenTelemetry, Prometheus, and Grafana; mean incident detection time dropped from 18 minutes to under 3.
- Authored the internal RFC for moving 14 services from on-prem to AWS EKS; led the actual migration over 9 months with zero customer-facing downtime.
- Designed a Postgres → Snowflake reverse-ETL job in Airflow that powered ops dashboards used by 200+ planners daily.

### Software Engineer, Initix (acquired by Quantum) — Seattle, WA
2017-08 – 2019-05
- Built REST APIs in Django for an early B2B logistics product (10k DAU); owned auth, billing, and webhook ingestion.
- Implemented async job processing with Celery + RabbitMQ, replacing an unreliable cron-based system; eliminated weekly on-call pages from the data team.
- Wrote the company's first integration test framework (pytest + Docker compose), bringing CI from manual to fully automated.

## Selected Projects

### Open-source: feast-onlinestore-aerospike (maintainer)
2023-01 – Present
Tech: Python, Aerospike, Feast
- Wrote the Aerospike online store adapter for Feast, used in production by 4 companies; merged into upstream after 3 RFC iterations.

### Side project: textbook-rag
2024-04 – 2024-09
Tech: PyTorch, FAISS, Llama 3, FastAPI
- Built a retrieval-augmented QA system over college physics textbooks; experimented with hybrid BM25 + dense retrieval and re-rankers (bge-reranker-v2).
- Wrote a blog post on chunking strategies that reached front page of HN.

## Education

### M.S. Computer Science, University of Washington
2015-09 – 2017-06
GPA: 3.85/4.0
- Focus: Distributed systems, ML systems.

### B.S. Software Engineering, Tsinghua University
2011-09 – 2015-06

## Skills
Languages: Python, Go, Java, SQL, TypeScript (basic)
ML / Data: PyTorch (intermediate), Feast, MLflow, Pandas, NumPy, scikit-learn
Infra: Kubernetes, KServe, Kafka, Flink, Spark, Airflow, Postgres, Redis, Aerospike, Snowflake
Cloud: AWS (EKS, MSK, RDS, S3), GCP (basic)
Tools: OpenTelemetry, Prometheus, Grafana, Terraform

## Publications
- "Tiered Caching for High-Throughput Feature Stores" — Internal Skyline whitepaper, 2024.

## Certifications
- AWS Certified Solutions Architect — Associate, 2021
