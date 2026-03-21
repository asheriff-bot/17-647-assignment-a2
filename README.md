# Assignment A2: BFF, JWT & Multiple Microservices

Python microservices for the bookstore e-commerce system, deployable on AWS with the provided CloudFormation template.

## Architecture

| Service              | Port | EC2 Instances        |
|----------------------|------|----------------------|
| Web BFF              | 80   | EC2BookstoreA, B     |
| Mobile BFF           | 80   | EC2BookstoreC, D     |
| Customer service     | 3000 | EC2BookstoreA, D     |
| Book service         | 3000 | EC2BookstoreB, C     |

- **External ALB** routes by `X-Client-Type`: `Web` → Web BFF, `iOS`/`Android` → Mobile BFF. Missing header → **400** (ALB default — request never reaches your BFF).
- **BFFs** check **JWT first (401)**, then **`X-Client-Type` (400)**. Use `shared/bff_auth.py` so order is guaranteed.
- **Internal ALB** routes `/customers*` → Customer service, `/books*` → Book service on **port 3000** (not 80).
- **`URL_BASE_BACKEND_SERVICES`** on every BFF container must be **`http://<InternalALBDNSName>:3000`**. If you point this at the **External** ALB or wrong port, you will see **400** or **502** on proxied calls.

## JWT Validation (BFFs)

- Token in `Authorization: Bearer <token>`.
- Payload must have: `sub` ∈ {starlord, gamora, drax, rocket, groot}, `iss` = "cmu.edu", `exp` in the future.

Create test tokens at [jwt.io](https://jwt.io) with HS256 and payload like:
`{"sub":"starlord","roles":"pilot","iss":"cmu.edu","exp":<future_epoch>,"usern":"Peter Quill"}`.

## Mobile BFF Response Transformations

- **Books**: In response body, replace the word `"non-fiction"` with the number `3`.
- **Customers**: Remove `address`, `address2`, `city`, `state`, `zipcode` from JSON responses.

## Prerequisites

- Docker
- AWS CLI (for deployment)
- After CloudFormation stack: Internal ALB DNS, DB cluster endpoint, DB credentials

## Database Setup

1. Get the Aurora writer endpoint from CloudFormation Outputs (`DBClusterEndpoint`).
2. From a machine that can reach the VPC (e.g. EC2 in the same VPC), run:
   ```bash
   mysql -h <DBClusterEndpoint> -u <DBUsername> -p < scripts/init_db.sql
   ```
   Use the `DBUsername` and `DBPassword` from stack parameters.

## Build Images

From the repo root (assign_2_aws):

```bash
docker build -t bookstore/customer-service ./customer_service
docker build -t bookstore/book-service ./book_service
docker build -f web_bff/Dockerfile -t bookstore/web-bff .
docker build -f mobile_bff/Dockerfile -t bookstore/mobile-bff .
```
(BFF images must be built from repo root so `shared/` is in context.)

## Run Locally (single host)

1. Start MySQL, create DB and tables (see `scripts/init_db.sql`).
2. Start backend services:
   ```bash
   docker run -p 3001:3000 -e DB_HOST=host.docker.internal -e DB_USER=root -e DB_PASSWORD=xxx -e DB_NAME=bookstore bookstore/customer-service
   docker run -p 3002:3000 -e DB_HOST=host.docker.internal -e DB_USER=root -e DB_PASSWORD=xxx -e DB_NAME=bookstore bookstore/book-service
   ```
3. Start BFFs (point to backend):
   ```bash
   docker run -p 8080:80 -e URL_BASE_BACKEND_SERVICES=http://host.docker.internal:3001 bookstore/web-bff
   docker run -p 8081:80 -e URL_BASE_BACKEND_SERVICES=http://host.docker.internal:3002 bookstore/mobile-bff
   ```
   For a single backend that serves both books and customers, use one URL with port 3000 and run both backends on different ports mapped to 3000 on one host, or use a local reverse proxy.

## Deploy on AWS (per EC2)

After the CloudFormation stack is created:

1. Get from **Outputs**: `InternalALBDNSName`, `DBClusterEndpoint`. Use stack **Parameters**: `DBUsername`, `DBPassword`.
2. **EC2BookstoreA** (Web BFF + Customer service):
   ```bash
   docker run -d -p 80:80 -e URL_BASE_BACKEND_SERVICES=http://<InternalALBDNSName>:3000 bookstore/web-bff
   docker run -d -p 3000:3000 -e DB_HOST=<DBClusterEndpoint> -e DB_USER=<DBUsername> -e DB_PASSWORD=<DBPassword> -e DB_NAME=bookstore bookstore/customer-service
   ```
3. **EC2BookstoreB** (Web BFF + Book service):
   ```bash
   docker run -d -p 80:80 -e URL_BASE_BACKEND_SERVICES=http://<InternalALBDNSName>:3000 bookstore/web-bff
   docker run -d -p 3000:3000 -e DB_HOST=<DBClusterEndpoint> -e DB_USER=<DBUsername> -e DB_PASSWORD=<DBPassword> -e DB_NAME=bookstore bookstore/book-service
   ```
4. **EC2BookstoreC** (Mobile BFF + Book service):
   ```bash
   docker run -d -p 80:80 -e URL_BASE_BACKEND_SERVICES=http://<InternalALBDNSName>:3000 bookstore/mobile-bff
   docker run -d -p 3000:3000 -e DB_HOST=<DBClusterEndpoint> -e DB_USER=<DBUsername> -e DB_PASSWORD=<DBPassword> -e DB_NAME=bookstore bookstore/book-service
   ```
5. **EC2BookstoreD** (Mobile BFF + Customer service):
   ```bash
   docker run -d -p 80:80 -e URL_BASE_BACKEND_SERVICES=http://<InternalALBDNSName>:3000 bookstore/mobile-bff
   docker run -d -p 3000:3000 -e DB_HOST=<DBClusterEndpoint> -e DB_USER=<DBUsername> -e DB_PASSWORD=<DBPassword> -e DB_NAME=bookstore bookstore/customer-service
   ```

Replace `<InternalALBDNSName>`, `<DBClusterEndpoint>`, `<DBUsername>`, `<DBPassword>` with actual values. Ensure images are available on each EC2 (push to ECR and pull, or build on each instance).

## API Summary

- `GET /status` – health check (all services); no JWT on BFFs for ALB.
- **Customer service**: `GET /customers`, `GET /customers?userId=...`, `GET /customers/<id>`, `POST /customers`.
- **Book service**: `GET /books`, `GET /books/<isbn>`, `GET /books/isbn/<isbn>`, `POST /books`.
- **BFFs** expose the same paths; call with `X-Client-Type: Web` or `iOS`/`Android` and `Authorization: Bearer <JWT>`.

## Project Layout

```
assign_2_aws/
├── .env.example            # Env var template (copy to .env; .env is gitignored)
├── .gitignore
├── CF-A2-cmu.yml           # CloudFormation template
├── customer_service/       # Customer microservice (port 3000)
├── book_service/           # Book microservice (port 3000)
├── web_bff/                # Web BFF (port 80)
├── mobile_bff/             # Mobile BFF (port 80)
├── shared/                 # JWT validation (used by BFFs)
├── scripts/
│   ├── init_db.sql         # DB schema and sample data
│   └── nginx-backend.conf  # Local backend router config
├── docker-compose.yml      # Local run (all services)
├── deploy.md               # Step-by-step build & AWS deploy
└── README.md
```

## Production readiness

- **Secrets**: Never commit `.env` or real credentials. Use `.env.example` as a template. In AWS, pass `DB_PASSWORD` and similar via `docker run -e`, ECS task definitions, or AWS Secrets Manager / SSM Parameter Store. If you previously committed a `.env` file, run `git rm --cached <path>/.env` and rotate any exposed keys.
- **.gitignore**: Covers `.env`, `*.pem`, Python cache, IDE files, logs, and local overrides. Commit only code and `.env.example`.
- **Dependencies**: `requirements.txt` uses pinned ranges (e.g. `flask>=2.0,<4`) for reproducible builds.
- **HTTPS**: For production, attach an ACM certificate to the External ALB and add an HTTPS listener (port 443) in the CloudFormation template.
- **Health checks**: All services expose `GET /status` (200) for ALB health checks; ensure target groups use this path.
- **Deployment**: See **deploy.md** for the full build-and-deploy sequence.
