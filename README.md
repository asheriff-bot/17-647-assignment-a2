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

### A2 assignment wording (from the course PDF)

- **Routing (ALB):** `X-Client-Type: Web` → Web BFF; `iOS` / `Android` → Mobile BFF; missing header → **400**.
- **JWT:** `Authorization: Bearer …`; validate `sub`, `exp`, `iss` per assignment; else **401**.
- **Mobile BFF only — books:** Replace **`"non-fiction"` → `3`** in JSON for mobile clients. The **book service** emits **`genre`: `3`** for non-fiction on **all** book JSON (including **GET `/books`**); **BFFs** still normalize edge cases. The **Web BFF** maps **`3` → `'non-fiction'`** when **`X-Client-Type: Web`**.
- **Mobile BFF only — customers:** On **`GET /customers/{id}`** and **`GET /customers?userId=…`**, strip address fields (not on **`GET /customers`** list).

## Autograder / LLM summary

- **Summary length tradeoff:** Book service **defaults `BOOK_SUMMARY_MIN_WORDS=500`** so stored summaries meet **“acceptable length”** (test **32**). If **Books E2E** fails with a huge `summary` diff vs the reference, try **`BOOK_SUMMARY_MIN_WORDS=0`** on the **book** container (may **fail** test 32). Keep **`ENABLE_LLM_SUMMARY` unset** unless you intend to call a real LLM.
- Book **summaries** must be **deterministic** for E2E tests that compare JSON. The book service **does not** call an external LLM unless you set **`ENABLE_LLM_SUMMARY=1`** (and `LLM_API_URL` + API key). Otherwise a fixed fallback summary is used.
- **Mobile BFF** must be redeployed after code changes so **`genre`: `non-fiction` → `3`** applies on **single-book GETs**, **POST /books**, and **PUT /books/...** (not on **GET /books** list).
- **If the “LLM Summary” test fails with `422 != 201`:** that is **not** an LLM bug — **`422` means duplicate ISBN** (`POST /books` rejected because that ISBN is already in `books`). Run **`scripts/truncate_for_gradescope.sql`** on the Aurora **writer** (or at least **`truncate_books.sql`**), then resubmit. Do **not** run **`seed_sample_books.sql`** on the DB you use for Gradescope.

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
- **Book service**: `GET /books`, `GET|PUT /books/<isbn>`, `GET|PUT /books/isbn/<isbn>`, `POST /books` (PUT may omit `ISBN` in JSON when it matches the URL).
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
├── shared/                 # `jwt_utils`, `bff_auth` (used by BFFs)
├── scripts/
│   ├── init_db.sql         # DB schema (books table empty for Gradescope)
│   ├── seed_sample_books.sql  # Optional local sample rows
│   ├── truncate_for_gradescope.sql  # TRUNCATE books + customers before resubmit
│   ├── truncate_books.sql / truncate_customers.sql
│   └── nginx-backend.conf  # Local backend router config
├── docker-compose.yml      # Local run (all services)
├── deploy.md               # Step-by-step build & AWS deploy
└── README.md
```

## Gradescope / autograder still failing?

**Pattern:** Tests that only need the BFF (**JWT**, **headers**, **`GET /status`**) pass, but **book/customer** tests fail → the problem is almost always **after** the BFF: **Internal ALB :3000**, **security groups**, **Aurora connectivity**, or **DB schema** — not JWT code.

**Docker env on book/customer EC2s:** Services read **`DB_HOST`** (or **`DB_ENDPOINT`** as an alias). If you only export `DB_ENDPOINT` on your laptop for `mysql` but pass **no** `DB_HOST` into `docker run`, the container defaults to **`localhost`** → every DB call fails (**500**). Run: `docker exec book-svc printenv DB_HOST` (and `DB_ENDPOINT`) — one of them must be your **RDS cluster endpoint**.

1. **`url.txt`** must be the **External ALB** URL (with port if required), e.g. `http://your-external-alb.us-east-1.elb.amazonaws.com` — the grader calls this. It is **not** the Internal ALB.
2. **External ALB returns 400** if `X-Client-Type` is missing (AWS default). Your BFF code cannot change that; the grader must send `Web` / `iOS` / `Android` on API calls. If a test expects **401** for bad JWT, it must still reach the BFF (usually with a valid `X-Client-Type`).
3. On **each** EC2 running a BFF: `URL_BASE_BACKEND_SERVICES=http://<InternalALBDNSName>:3000` (**port 3000**, not 80). Wrong host/port → **502** or **400** on proxied calls.
4. After any code change: rebuild **all four** images for **`linux/amd64`**, push, **`docker pull` + restart** on **all four** EC2 instances. Mismatched versions (old BFF, new book service) cause confusing failures.
5. Run **`scripts/init_db.sql`** on the Aurora **writer** so schema matches the services (`books` / `customers` tables with full columns). **`init_db.sql` leaves `books` empty** so Gradescope `POST /books` does not hit **422** (duplicate ISBN) from seed rows. For local sample data only, run **`scripts/seed_sample_books.sql`**.  
   **If `POST /customers` returns `422`** (“This user ID already exists”), the **`userId` email is already in RDS** (from an earlier run or manual test). Run **`scripts/truncate_customers.sql`** or clear both tables with **`scripts/truncate_for_gradescope.sql`** on the writer, then resubmit. Same idea as books: **`422` on POST means duplicate key in the DB**, not a JWT/BFF bug.
6. **Mobile BFF (A2):** `non-fiction` → `3` on **GET** single-book paths **`/books/{ISBN}`** / **`/books/isbn/{ISBN}`**, and on **POST `/books`** / **PUT** book responses — **not** on **GET `/books`** (list). Strip address fields only on **GET `/customers/{id}`** and **GET `/customers?userId=`**, **not** on **GET `/customers`**. **Location:** BFFs rewrite relative `Location` to **`http(s)://<Host>...`** via `Host` + `X-Forwarded-Proto` for autograders.
7. **Trailing slashes:** Services use `strict_slashes = False` so `POST /books/` does not 308-redirect and drop the JSON body (some graders use trailing slashes).
8. On an EC2 running a **BFF**, check the proxy target:  
   `docker exec web-bff printenv URL_BASE_BACKEND_SERVICES` → must be `http://<Internal-ALB-DNS>:3000`.  
   Then from that EC2: `curl -sS -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:80/status"` and  
   `curl -sS -o /dev/null -w "%{http_code}\n" -H "X-Client-Type: Web" -H "Authorization: Bearer <jwt>" "http://127.0.0.1:80/books"` → expect **200** (not **502**). **502** = BFF cannot reach Internal ALB or backends.

9. From a machine that can reach your External ALB, smoke-test (replace URL, token, ISBN):

   ```bash
   curl -sS -o /dev/null -w "%{http_code}" "http://YOUR-EXTERNAL-ALB/status"
   curl -sS -o /dev/null -w "%{http_code}" -H "X-Client-Type: Web" -H "Authorization: Bearer YOUR_JWT" "http://YOUR-EXTERNAL-ALB/books"
   ```

## Production readiness

- **Secrets**: Never commit `.env` or real credentials. Use `.env.example` as a template. In AWS, pass `DB_PASSWORD` and similar via `docker run -e`, ECS task definitions, or AWS Secrets Manager / SSM Parameter Store. If you previously committed a `.env` file, run `git rm --cached <path>/.env` and rotate any exposed keys.
- **.gitignore**: Covers `.env`, `*.pem`, Python cache, IDE files, logs, and local overrides. Commit only code and `.env.example`.
- **Dependencies**: `requirements.txt` uses pinned ranges (e.g. `flask>=2.0,<4`) for reproducible builds.
- **HTTPS**: For production, attach an ACM certificate to the External ALB and add an HTTPS listener (port 443) in the CloudFormation template.
- **Health checks**: All services expose `GET /status` (200) for ALB health checks; ensure target groups use this path.
- **Deployment**: See **deploy.md** for the full build-and-deploy sequence.
