# Deployment plan (Oct 18, 2026; planning only, nothing built or signed up)

Written for the owner, who must be able to explain every line. Docs only: no code, no account, no model call and no paid command was used. Every price, limit or policy below comes from an official page I read on **2026-10-18** (the URL is next to it). Where I could not confirm something from an official page it says **unconfirmed**. Figures I measured on this machine say "measured". Arithmetic is mine and is shown.

> **Update, Oct 18, 2026 (Part A of the build):** the build is described in [docs/deploy-runbook.md](deploy-runbook.md) and "Deployment Part A" in `docs/decisions.md`. Where this plan and the build differ, the build wins: the monthly cap is the current UTC month at $5 (not a rolling 30 days; the owner chose it, caveat in the runbook); the visitor address comes from a shared secret plus `x-real-ip` in the API (no uvicorn proxy headers, no `X-Forwarded-For` rewrite in Caddy); the page forwards through `web/proxy.ts` (a header cannot be added by a `next.config` rewrite, and a `vercel.json` header transform was untested); Postgres is on an internal Docker network with no published port; `data/` is a bind mount, not baked into the image; the kill switch reply reads "The assistant is temporarily paused. Please check back later."; the daily cap stayed at $1.

> **Update, Oct 18, 2026 (Lightsail):** the owner chose **AWS Lightsail**, not EC2. Instance `cta-server`, Ubuntu 24.04 LTS, the $12 plan (2 GB RAM, 2 vCPUs, 60 GB SSD, 3 TB transfer), region **Ohio (us-east-2a)**, dual-stack, static IP `cta-ip` = `3.135.33.79` attached, snapshots off, firewall rules HTTP 80, SSH 22 and HTTPS 443 (IPv4 only), a DuckDNS name with no IPv6 record. The EC2, security group, EBS, Elastic IP and `t3.small` text below is replaced; the cost is **$12 a month, $72 for 6 months**. Plan contents and prices are from the owner's console, not from an official page I read; whether the free-plan credits pay for Lightsail is **unconfirmed** (the owner checks Billing and Credits). The step order is in [docs/deploy-runbook.md](deploy-runbook.md).

State checked first: repo `~/city-tech-assistant`, branch `master`, working tree clean, HEAD `d186e09` (a data-only commit on top of `45d6765`). Local Docker Postgres is `pgvector/pgvector:0.8.7-pg17`.

## Summary table

| Item | Recommended default | Monthly cost | Source URL | Date read | Status |
|---|---|---|---|---|---|
| Web page | Vercel Hobby, free `vercel.app` address | $0 | https://vercel.com/docs/plans/hobby | 2026-10-18 | confirmed (non-commercial use only) |
| Server plan | AWS Free account plan: $100 signup credit plus up to $100 more by activities. Credits last 12 months; the Free plan itself ends at 6 months or when credits run out | $0 cash while credits last | https://aws.amazon.com/free/terms/ and https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html | 2026-10-18 | confirmed; **unconfirmed** that credits pay for Lightsail |
| Server | AWS Lightsail `cta-server`: $12 plan (2 GB RAM, 2 vCPUs, 60 GB SSD, 3 TB transfer), Ubuntu 24.04 LTS, Ohio (us-east-2a) | **$12 a month, $72 for 6 months** | owner's Lightsail console | 2026-10-18 | from the owner's console, not an official page |
| Static IP | `cta-ip` (3.135.33.79), attached | $0 while attached (charged when not attached) | https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-static-ip-addresses-in-amazon-lightsail.html | 2026-10-18 | confirmed |
| Disk, IPv4, transfer | included in the plan (no separate disk or IPv4 line) | $0 extra | owner's console | 2026-10-18 | **unverified** on an official page |
| Snapshots | off; the owner's own `pg_dump` is the backup | $0 (snapshots are billed separately) | owner's console | 2026-10-18 | **unverified** |
| **AWS total** | | **$12 a month** | arithmetic: 12 x 6 | 2026-10-18 | 6 months = $72, see 1.4 |
| Fallback server | Hetzner CX23 (2 vCPU, 4 GB) | EUR 5.49 + 0.50 IPv4 = EUR 5.99, excluding VAT | https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/ and https://docs.hetzner.com/cloud/servers/primary-ips/overview/ | 2026-10-18 | prices confirmed; **availability unconfirmed** (3.1) |
| Browser to API path | Same-origin `/api/*` rewrite on Vercel to the server (the app already does this) | $0 | https://vercel.com/docs/routing/rewrites | 2026-10-18 | confirmed (header behaviour); timeout **unconfirmed** |
| HTTPS hostname for the server | Free DuckDNS name plus Caddy certificate | $0 | https://www.duckdns.org/ | 2026-10-18 | partly confirmed: free, terms page exists; limits unconfirmed |
| Paid hostname alternative | A `.com` at a registrar | $11.08 a year (about $0.92 a month) | https://porkbun.com/products/domains | 2026-10-18 | confirmed for Porkbun; Cloudflare states no price |
| OpenAI cap | Project hard limit $7 a month plus alerts, plus an app-side monthly cap of $5 | $0 to $7 (expected about $1 to $2) | https://developers.openai.com/api/docs/guides/spend-limits | 2026-10-18 | docs confirmed; real enforcement **unconfirmed** (5.1) |
| LangSmith | Developer (free) plan, no card on file, scrubbed tracing ON | $0 | https://www.langchain.com/pricing and https://docs.langchain.com/langsmith/billing | 2026-10-18 | confirmed; behaviour past the limit only partly |
| Budget alert | AWS Budgets cost budget with email alerts | $0 | https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/ | 2026-10-18 | confirmed |

Expected cash cost while the AWS credits last: **$0** ($12 a month of credits, $72 over the 6 months) (plus a domain if you choose one). Expected OpenAI cost: measured $0.00034 per request, so 100 questions a day is about $1.03 a month.

---

## 1. AWS Free plan

### 1.1 What the free plan is

| Question | Answer | Source (read 2026-10-18) |
|---|---|---|
| Credit at signup | "USD $100 in credits after you create an account regardless of your account plan." | https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html |
| Extra credits | Up to $100 more "by completing activities" in the Explore AWS widget. Listed activities (a Lightsail instance may not count as the EC2 one: **unverified**): launch an EC2 instance, use a Bedrock playground model, **set up a cost budget with AWS Budgets**, build a Lambda web app, create an RDS database. Four of the five say they incur charges deducted from the credits; the Budgets one does not. **The dollar value of each activity is not on the page: unconfirmed.** | https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans-activities.html |
| How long | "Your free account plan ends after six months or when your credits are fully used - whichever occurs first." Activities must be done within 6 months of opening the account. | free-tier-plans.html above; https://aws.amazon.com/free/free-tier-faqs/ |
| When it ends | The account closes automatically and you "lose access to your resources and data. AWS retains your content for 90 days before permanently deleting your account." You can upgrade to a Paid plan within 90 days; "Any remaining credits from your free account plan are automatically applied to future AWS bills." | free-tier-plans.html |
| Credit card | The FAQ (read through a summarizing tool, not word for word) says not required for most new customers but "may" be requested to verify identity. **Unconfirmed**: the owner reports what the signup actually asks (step 2 in section 8). | https://aws.amazon.com/free/free-tier-faqs/ |
| Services allowed | "Access to select AWS services and features". The excluded list is not on the doc pages ("a subset ... that would immediately consume the entire Free Tier credit amount"). EC2 is allowed: "Use credits to access Amazon EC2 features in both Free and Paid plans." | https://aws.amazon.com/free/compute/lightsail-vs-ec2/ ; FAQ above |
| Instance type | Not relevant any more: the server is a Lightsail instance, so the EC2 size list (`t3.micro`, `t3.small` and others) no longer applies. Whether Lightsail is paid by free-plan credits is **unconfirmed**; the page I read in the first draft said only that Lightsail has a 90-day trial "with the Paid plan" | https://aws.amazon.com/free/compute/lightsail-vs-ec2/ |
| Lightsail | The owner's account accepted the Free account plan when the instance was created. The free-terms page does not mention Lightsail (https://aws.amazon.com/free/terms/, read 2026-10-18). **Unconfirmed** whether credits pay for it: the owner checks Billing and Credits. | https://aws.amazon.com/free/terms/ |
| Other promotions | Free plan accounts "are not eligible for other promotional credits and discounts." Joining AWS Organizations (and a few other things listed) upgrades the account to Paid automatically: do not join one. | free-tier-plans.html |
| Credit expiry | The terms page: "Free Tier Credits expire twelve months from the date you opened your account"; "Free Plan accounts will expire (1) six months from the date you opened your account" or when credits are used up, whichever comes first. So at month 6 the account can be upgraded to a Paid plan and unused credits remain until month 12 (an FAQ page I read earlier gave a conflicting 6-month answer for credits; the terms page is the one to trust). | https://aws.amazon.com/free/terms/ |
| Sensitive data | "Free Plan accounts are provided for evaluation purposes and should not be used for processing sensitive data." The demo stores only redacted questions, no accounts and no student records, and the page says so; the README refresh adds one honest line about it (runbook step 28). | https://aws.amazon.com/free/terms/ |

### 1.2 Static IP, firewall and transfer (Lightsail)

- Static IP: "There are no costs associated with static IP addresses when they are attached to a Lightsail instance. However, static IP addresses incur a charge when they aren't attached to an instance." Without one, "each time you stop or restart your instance, Lightsail assigns a new public IP address." https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-static-ip-addresses-in-amazon-lightsail.html (read 2026-10-18). `cta-ip` (3.135.33.79) is attached, so no IP update job is ever needed for DuckDNS.
- Firewall: rules only allow traffic; the guide I read says each instance has **two** independent firewalls, one for IPv4 and one for IPv6, and recommends opening port 22 only to the address that needs it (https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-firewall-and-port-mappings-in-amazon-lightsail.html, read 2026-10-18). The owner's console shows **one table** for both: **unverified**. The rules now: HTTP 80 (any), SSH 22 (any, with Lightsail browser SSH) and HTTPS 443 (IPv4 only); the DuckDNS name has no IPv6 record so nobody is sent to a closed port. SSH is tightened only after the test day.
- Disk, IPv4 and transfer: the $12 plan includes a 60 GB SSD and 3 TB of transfer, and there is no separate IPv4 charge, per the owner's console (**unverified** on an official page). One answer is about 0.4 KB of text plus sources, so a month is far under 1 GB.
- Snapshots are off (billed separately, **unverified**); the backup is the index dump (section 7.3).

### 1.3 Burn

| Line | Per month |
|---|---|
| Lightsail $12 plan (instance, SSD, transfer, attached static IP) | $12 |
| **Total** | **$12** (about $0.40 a day); **$72 for 6 months** |

### 1.4 Does 6 months fit inside the credits?

- 6 months x $12 = **$72**, inside the $100 signup credit alone, *if* the credits pay for Lightsail (**unconfirmed**; Billing and Credits will show it).
- The Free plan ends at 6 months (or when credits are used up). The credits last 12 months (terms page, read 2026-10-18), so the owner can upgrade to a Paid plan at month 6 and keep the unused credits until month 12: about $100 - $72 = $28 left, plus any activity credits, which would cover roughly two more months of the $12 plan, if credits apply to Lightsail.
- Either way the Free plan has a hard end date: signup date plus 6 months. After an upgrade the instance costs $12 a month in cash once the credits are gone; Hetzner (section 3) is the alternative.
- Free plan accounts are "for evaluation purposes and should not be used for processing sensitive data" (https://aws.amazon.com/free/terms/, read 2026-10-18). The demo holds redacted questions only; the README says it plainly.

---

## 2. Size: what the app needs (measured)

All measured today on this machine, with no model call.

| What | Measured | How |
|---|---|---|
| Chunks | **619** (197 `catalog_course`, 115 `program`, 112 `department`, 67 `faq`, 39 `policy`, 31 `howto`, 29 `contacts`, 26 `aid`, 3 `calendar`) | `select doc_type, count(*) from chunks` |
| Embedding data | 3.7 MB (619 x 1,536 floats x 4 bytes) | `pg_column_size(embedding)` |
| `chunks` table with its indexes | **6.9 MB** (heap 1.0 MB, GIN full-text index 496 kB, primary key 48 kB, rest is TOAST/embeddings) | `pg_total_relation_size` |
| pgvector index | **none**. Only `chunks_pkey` and `chunks_tsv_idx` exist; the code has no HNSW/IVFFlat (grep of `src/` and `db/`). Search is an exact scan of 619 rows, so there is no index memory to size. | `pg_indexes` |
| Whole database | **25 MB** (eval_runs 1.1 MB, request_logs 3.9 MB, calendar_events 64 kB) | `pg_database_size` |
| `pg_dump -Fc` of the whole database | 5.5 MB (4.5 MB without `request_logs` and `eval_runs`) | measured |
| API memory | **118 MB resident** for the uvicorn worker after start-up and one `/health` call (the three-process tree: 3.6 + 32.7 + 117.8 MB; the last is the server). **Per-request peak not measured**: it needs a model call, which this session may not make. | `/proc/<pid>/status`, started on a spare port and stopped |
| Postgres container | 85 MiB resident idle, `shared_buffers` 128 MB default | `docker stats` |
| `request_logs` growth | average row about **2.2 KB** (4.7 KB max) over 704 API rows; 1,655 eval rows average 1.1 KB. Real daily counts so far: 59, 17, 555, 73. At 100 questions a day that is about 0.22 MB a day, and with the 30-day purge the table stays near **7 MB**. Without any purge, a year at 100 a day is about 80 MB. | `pg_column_size(r.*)`, `count(*)` per day |
| Per-request cost | average **$0.00034**, max $0.00148 (700 API rows with a cost) | `request_logs` |
| Latency | median 2.9 s, p95 10.3 s (same rows) | `request_logs.latency_ms` |
| Data the API reads from disk | `config/contacts.yaml`, `data/calendar/calendar_events.json`, `data/processed/courses` (808 kB; start-up check in `src/cta/api/checks.py`). `data/processed` is git-ignored, so the server needs a copy shipped by hand (3.5 MB total). | `du`, `checks.py` |

**Estimate for the whole box** (my arithmetic, not a measurement): API 118 MB + per-request working memory (unmeasured, assume up to 100 to 200 MB under a few parallel requests) + Postgres 85 MB (up to about 200 MB with caches) + Caddy about 30 MB + Docker daemon and OS about 400 MB = roughly **0.8 to 1.0 GB**.

**Recommendation: the $12 plan (2 GB RAM, 2 vCPUs).** A 1 GB plan would leave almost no headroom and an out-of-memory kill would take the site down. The evidence gap (per-request peak memory) is closed on the test day: watch `docker stats` during the 20-question run. A 2 GB swap file is added on the server (runbook step 5).

Disk: the plan's 60 GB SSD holds the OS (about 8 GB), the Docker images (Python app image with its dependencies and the pgvector image; the app image is 435 MB, measured in the rehearsal), the database (25 MB) and a few dump files (5.5 MB each).

Build note for the build session, from `docs/phase4-plan.md` section 7: the image must also ship `data/processed/courses` and `data/calendar/`; the fresh-clone check already shows the API will not start without them.

---

## 3. Fallback: Hetzner

| Plan | Spec | Price per month, excluding VAT, excluding IPv4 | Source (read 2026-10-18) |
|---|---|---|---|
| CX23 (Intel/AMD, cost-optimized) | 2 vCPU, 4 GB, 40 GB NVMe, 20 TB traffic | EUR 5.49 (was 3.99) | https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/ |
| CAX11 (Arm, cost-optimized) | 2 vCPU, 4 GB, 40 GB | EUR 5.99 (was 4.49) | same |
| CPX22 (regular) | 2 vCPU, 4 GB, 80 GB | EUR 19.49 (was 7.99) | same |
| Primary IPv4 | one address | EUR 0.50 (USD 0.60) a month excluding VAT | https://docs.hetzner.com/cloud/servers/primary-ips/overview/ |

- **With IPv4:** CX23 = 5.49 + 0.50 = **EUR 5.99**; CAX11 = EUR 6.49. **Without IPv4** it is the table price, but the page does not say that a server can run without a Primary IPv4 and Vercel and most home networks need IPv4, so use the with-IPv4 figure. The doc says "Primary IPv6s are free."
- **VAT:** "All prices are excluding VAT"; the page points to the German price list for 19 % VAT. What applies to the owner's country and billing type is **unconfirmed**. If 19 % applied: EUR 5.99 x 1.19 = EUR 7.13.
- The price change took effect for new orders "starting on the 15 June 2026; 8 AM CEST".
- **Availability is the problem.** The Hetzner plan pages (https://www.hetzner.com/cloud/cost-optimized/ and /regular-performance/) show every plan as "currently unavailable" and show blank prices when read without JavaScript, so I **cannot confirm that a CX23 can be ordered today**. A third-party report (not used for any figure) says the cost-optimized line had limited availability since June. If CX23 and CAX11 cannot be ordered, the cheapest regular plan on the price page is CPX22 at **EUR 19.49**, about the same as the AWS burn, and your EUR 5.50 to 6 estimate does not hold. The owner confirms in the Hetzner console before relying on this fallback.
- Hetzner bills hourly with a monthly cap and bills powered-off servers until deleted (https://docs.hetzner.com/cloud/billing/faq/). No free credits: it needs a card from day 1.

**What the README says when the AWS period ends** (replace the "Status" line, after the owner fills the dates; nothing to write until the test day passes):

> Status: live demo at <link>, running on free cloud credits until <date>. After that date it goes offline unless I move it to a paid host. The recorded walkthrough stays available either way. Not affiliated with City Tech or CUNY.

And on the day: stop the instance (or let the account close), then make the README line read "The live demo ended on <date> when the free hosting credits ran out. The recorded walkthrough is below." Take the link out the same day, so a visitor never lands on a dead page. If moved to Hetzner, the line states the new end date and nothing else changes: same Docker files, restore the dump (section 7.3).

---

## 4. HTTPS and the address

### 4.1 How the app calls the API today (read from the repo)

- The browser calls only `fetch("/api/ask")` and `fetch("/api/feedback")` on its own origin (`web/lib/api.ts`, lines 114 and 144).
- `web/next.config.mjs` rewrites `/api/:path*` to `API_URL` (default `http://127.0.0.1:8000`). So the browser never talks to the API host. Consequences:
  - **CORS: none needed.** The browser sees one origin. Do not add CORS to the API.
  - **Mixed content: none.** The page is HTTPS on `vercel.app` and every browser request is to that same HTTPS origin.
  - The `API_URL` is read when Next builds the rewrite. On Vercel I expect it at build time, so changing it needs a redeploy (**unconfirmed**; check on the first deploy).
- The API itself reads the visitor with `request.client.host` in exactly one place, `Guard.visitor_key` (`src/cta/api/guard.py`), and hashes it with a start-up salt. A test (`tests/test_requestlog.py:314`) forbids `x-forwarded-for` anywhere in `src/cta/api`.

### 4.2 The trap: the rate limiter behind a proxy

With the path browser -> Vercel -> server (-> Caddy -> API) the API's connection address is the proxy's, not the visitor's. **Every visitor would share one counter**, so the whole world would be limited to 10 questions a minute and 100 a day. This is already written down in `docs/decisions.md` ("Deployment note").

What the providers say:
- Vercel forwards the visitor's address to an external origin: "`x-real-ip`: The public IP address of the visitor", "`x-forwarded-for`: The public IP address of the visitor". https://vercel.com/docs/routing/rewrites
- Uvicorn: "Only trust proxies you control. Incorrectly trusting other clients can lead to malicious actors spoofing their apparent client address." and `"*"` only "when you know you can trust all values within the forwarded headers". https://uvicorn.dev/deployment/ . The page does not state the defaults of `--proxy-headers` and `--forwarded-allow-ips`: **unconfirmed**; set both explicitly.
- Vercel documents a shared-secret pattern: set a secret request header on the rewrite and have the origin reject requests without it ("Restricting your origin to Vercel traffic", same page). It uses a `vercel.json` `routes` transform; whether that combines with the Next.js `rewrites` in `next.config.mjs` is **unconfirmed** (test on the first deploy; the fallback is a small Next route handler that adds the header).

Design (no code now):
1. Caddy checks the secret header; anything without it gets a 403. This closes the "someone calls the origin directly and fakes `X-Forwarded-For`" hole.
2. Caddy sets `X-Forwarded-For` from Vercel's `X-Real-IP` (only after the secret check passed).
3. The API container runs uvicorn with `--proxy-headers` and `--forwarded-allow-ips` set to the Docker network where only Caddy can reach it; the Guard code does not change, and the `x-forwarded-for` test keeps passing because uvicorn, not the app, reads the header.
4. `HOST` in `src/cta/api/__main__.py` is hard-coded to `127.0.0.1`; inside a container it must listen on the container network address. That file and a Dockerfile are the build session's work.
5. Caddy's access log stays off. Caddy's docs: access logs are "enabled only when you use the `log` directive". https://caddyserver.com/docs/caddyfile/directives/log . So no address reaches a log file. Check once on the server.
6. Expose only what the page uses. Today `/api/:path*` would also publish `/api/health` (it shows the commit, the spend today and the block counts) and `/docs`. Change the rewrite to two sources, `/api/ask` and `/api/feedback`, and have Caddy allow only `POST /ask` and `POST /feedback`. The owner reads `/health` over SSH on `127.0.0.1`.

If the secret header cannot be made to work, the cost damage is still bounded by the app-side daily and monthly caps (section 5); only the per-visitor limit would be spoofable.

### 4.3 The three options for the server's hostname

The server needs a hostname because the Vercel-to-server hop carries question text, and a plain `http://IP` rewrite would send it unencrypted (and I could not confirm Vercel accepts it). A proxy through Vercel fixes CORS and mixed content for the browser, but it does **not** remove the need for a certificate on the server.

| Option | Yearly cost | Pros | Cons |
|---|---|---|---|
| A. Buy a domain | **$11.08 a year** for a `.com` at Porkbun (registration and renewal), https://porkbun.com/products/domains . `.dev` is $12.87 after the first year. Cloudflare Registrar says it sells "at or below" cost but its page states no `.com` price, **unconfirmed**. | Stable, owned, boring; Caddy gets a Let's Encrypt certificate; can keep the name after AWS ends | Costs money and needs a card; one more account |
| B. Free hostname | $0. DuckDNS is "free dynamic DNS hosted on AWS", funded by donations, sign-in through Google/GitHub/Reddit, no uptime statement. https://www.duckdns.org/ . The FAQ URL I tried was a 404, and the number of free names is **unconfirmed**. `duckdns.org` is on the Public Suffix List, so Let's Encrypt counts each name separately (limit "50 certificates ... per registered domain ... every 7 days", https://letsencrypt.org/docs/rate-limits/) | No cost, no card; set once and use | Depends on a donation-funded service with no stated uptime; its token is one more secret |
| C. A cloud provider's own hostname | $0 | No signup | Not used: a Lightsail static IP has no stable provider hostname I confirmed, and whether Let's Encrypt issues for such names is **unconfirmed** |

Vercel proxying is not an alternative to A or B; it is what the app already does, and it is combined with one of them.

**Recommendation:** keep the Vercel proxy (no code change to how the page calls the API) and use **B, a DuckDNS name, with Caddy's automatic certificate**. It is the simplest free option that keeps the question text encrypted on every hop. Test day proves it: if the certificate issues and renews cleanly, keep it. If DuckDNS misbehaves, buy a `.com` (about $0.92 a month), because only DNS changes. The Lightsail **static IP** `cta-ip` keeps the address across stops; set the DuckDNS IPv4 address to it and leave IPv6 empty (HTTPS is open on IPv4 only).

The Vercel project's `API_URL` is then `https://<name>.duckdns.org`, and the free `*.vercel.app` address is the public address for now.

Vercel Hobby: non-commercial, personal use only ("the Hobby plan restricts users to non-commercial, personal use only"); included usage is 100 GB Fast Data Transfer and 1,000,000 CDN requests a month; exceed a limit and "you will have to wait until 30 days have passed before you can use the feature again". https://vercel.com/docs/plans/hobby (page dated 2026-09-14). A portfolio demo with no income fits. The rewrite time limit for an external origin is not stated, and our p95 is 10.3 s with a 45 s request cap: **unconfirmed, test with the slowest question on the test day**.

### 4.4 Privacy side effects of the hosting choice (for the notice)

The notice says "No IP address and no cookies are stored." That stays true of our database and of the app (the hash lives in memory only, cleared on restart; the owner's note "stored hashed" really means "held in memory", and I recommend keeping it that way). But Vercel and AWS see network addresses in their own logs (Hobby keeps "1 hour of logs" of runtime logs, same Vercel page). Section 6.4 adds one sentence for that.

---

## 5. OpenAI cost control

### 5.1 What the dashboard offers (official)

Source: https://developers.openai.com/api/docs/guides/spend-limits and https://developers.openai.com/api/docs/guides/production-best-practices , read 2026-10-18.

- Both limits exist at the **organization** and at the **project** level, in a "Monthly spend limit" field (project: Project settings, Limits).
- **Spend alerts are notification-only**: "they send a notification and API traffic continues."
- **A hard limit is a separate toggle**, "Enforce a hard limit". At the limit, affected requests return HTTP `429` with code `project_spend_limit_exceeded` (project) or `organization_spend_limit_exceeded` (organization).
- "Enforcement is not instantaneous, so recorded spend can slightly exceed the configured amount." Resets with the next monthly cycle.
- So the dashboard does offer a real hard stop, plus alerts. **Caveat, unconfirmed:** a search result summarized a community forum post in which a user says OpenAI support told them project limits are notification-only. That is a single third-party report that contradicts the official page. I did not read the thread. So: do not rely on the dashboard alone. The owner tests the hard limit once (step 6 of section 8, optional, costs under a cent) and the app-side caps below are the control I treat as primary.

Recommended dashboard setup: a **new project** for this deployment with its own API key; monthly spend limit **$7 with "Enforce a hard limit" on**; alerts at $3 and $5; do not reuse the development key.

### 5.2 The app already has these controls (read from `docs/decisions.md` Stage 1 and `src/cta/api/guard.py`)

Per-visitor limit 10 a minute and 100 a day (in memory, address hashed); a **daily spend cap of $1.00** summed from `request_logs` (UTC day); a kill switch (config flag, env `CTA_API_DISABLED`, or the file `data/api_disabled`); timeouts 15 s per model call and 45 s per request. Live today: `/health` shows `spend_cap_usd: 1.0`.

Gaps for a public site:
1. **$1.00 a day is $30 a month, above your $7.** Nothing caps the month.
2. **No cap on the total number of requests** (cost per request varies, e.g. a flood of failed or long requests; the spend estimate for a failed request is a flat $0.002).
3. The per-visitor day limit of 100 is generous for one student.
4. If the cap query fails the request is allowed (fail open, an earlier owner decision); `spend_check_failures` in `/health` counts it.

### 5.3 Design (no code now)

Keep the existing order in `Guard.stage1`: kill switch, per-visitor limit, then caps. Add, with every number a config key and an environment override like the others:

| Key (block `guardrails:` in `config/models.yaml`) | Proposed default | Why |
|---|---|---|
| `rate_per_minute` | 10 (unchanged) | 11th question in a minute is refused |
| `rate_per_day` | **40** (from 100) | one student rarely asks more than a few; keeps one visitor from using a day's budget |
| `daily_request_cap` (new) | **400** model-using requests per UTC day, all visitors | at the measured $0.0004 a request this is about $0.16 a day, about $4.80 a month if hit every day |
| `daily_spend_cap_usd` | **0.30** (from 1.00) | a bad day cannot consume the month; failed requests count $0.002 each |
| `monthly_spend_cap_usd` (new) | **5.00**, summed over the **last 30 days** | below the $7 OpenAI hard limit, so the app stops first and the OpenAI limit is the backstop for enforcement lag and for embeddings of the unlogged |

Why a rolling 30 days: the purge command deletes API rows older than 30 days (`src/cta/api/purge.py`, and the notice says 30 days), so a calendar-month sum would lose the early days of a 31-day month. A rolling 30-day sum matches what the table keeps, so no new table or migration is needed. The cost: it is not aligned to OpenAI's billing month; that is why the app cap is $2 below the OpenAI limit.

Behaviour: a new fixed reply per new reason, same contract as the existing ones (HTTP 200, `answer_type: "guardrail"`, `how_found.route_detail` = the reason, a log row with `status = blocked_<reason>`, `/health.blocked` count, no model call):
- `daily_requests`: "The assistant has reached its limit for today. Please try again tomorrow." (same text as the existing `daily_cap` reply)
- `monthly_cap`: "The assistant has reached its limit for now. Please check back later."

Files where it would go:
- `config/models.yaml` (new keys and defaults) and its start-up validation (the code that validates `guardrails:` and the environment overrides; a bad value must stop the API with a fixed message).
- `src/cta/api/guard.py`: `TEXTS`, `BLOCK_REASONS`, the new checks next to the existing spend check, reusing the 10-second `spend_cache_s` so a burst makes one query. The `_unlogged` memory total must be added to the monthly sum, as it is for the day.
- `src/cta/api/app.py`: `/health` gains `spend_month_usd`, `requests_today`, `monthly_cap_reached` (numbers only, like the others); the request count query reads the `request_logs` rows of `source = 'api'` with `status = 'ok'` plus failed statuses since 00:00 UTC.
- `tests/test_guard.py`: boundary tests at the cap minus 0.001 and at the cap, the UTC midnight and the 30-day edge, no model call when blocked, `/health` has exactly the new keys.
- `docs/decisions.md`: a pre-registered keep rule written before the code, as for Stage 1.
- `web/` types if the page lists `route_detail` values (check at build time), and the README "Safety and cost controls" paragraph.

Decision for you (not mine): keep the "fail open" rule on a counter error, or fail closed for the public site. With the OpenAI hard limit behind it, I would keep fail open and watch `spend_check_failures`; with the community report in 5.1 unresolved, fail closed is the safer choice. You choose.

---

## 6. LangSmith

### 6.1 Free plan facts

| Question | Answer | Source (read 2026-10-18) |
|---|---|---|
| Free plan | Developer: "Up to 5k base traces / mo, then pay-as-you-go"; "Maximum of 1 seat (free)" | https://www.langchain.com/pricing |
| Retention | "Base traces have a shorter retention period of 14 days." Extended is 180 days and costs more. | same; https://docs.langchain.com/langsmith/billing |
| Past the limit | Personal organizations are "limited to 5,000 traces per month until a credit card is added"; without a card you are "rate limited, not billed". **Whether traces past 5,000 are dropped or queued is not stated: unconfirmed.** After you add a card the limit is removed and "you will be charged for any excess traces". | https://docs.langchain.com/langsmith/billing |
| Other ceilings | Without a payment method: 50,000 events an hour, 500 MB an hour; a run created and then updated counts as 2 events. | https://docs.langchain.com/langsmith/administration-overview |
| Setting a usage limit | Settings -> Billing and Usage -> Usage limits; "Enter a spend limit for the selected workspace" and LangSmith sets the trace limits to match, including the free allocation. | https://docs.langchain.com/langsmith/billing |

**Recommendation: do not add a card.** Then the 5,000-trace limit is the ceiling and nothing can be billed. The "usage limit" page is only meaningful once a card exists; the owner opens it anyway and reports what it shows (section 8).

### 6.2 Traces per question

`src/cta/api/tracing.py`, `Tracing.request`: one `ls.trace(name="ask", ...)` root per served request, inside which the graph steps and the OpenAI calls are child runs. A trace is the root with its children, so **one served question creates one trace**; the child runs are events, not extra traces (the docs page does not define "trace" itself, so this is my reading of the code plus LangSmith's trace/run wording: **unconfirmed on how the bill counts it**; the Usage page will show it after the test day). A request blocked by a guardrail (including the new caps) returns before the tracing context opens, so it creates **0 traces**. At the proposed 400-request daily cap the ceiling of 5,000 would be reached after 12.5 days of maximum traffic; at 100 questions a day (3,000 a month) it is never reached. If the limit is hit tracing stops working, not the assistant: the client has an error handler that logs a fixed warning with no payload (`UPLOAD_WARNING`, `tracing.py`). I have not run this failure; test it by lowering the limit on the test day.

### 6.3 Where the switch lives

Three things must all be present (docstring of `src/cta/api/tracing.py`, `config/models.yaml` lines 150 to 154, `.env.example`):
1. `tracing.enabled: true` in `config/models.yaml` (today `false`). The only way to set it is a file edit; there is no environment override. For the server I recommend a tiny later change so the server's compose file can set it without editing a tracked file (a build-session decision).
2. `CTA_TRACING=on` in the server's `.env`.
3. `LANGSMITH_API_KEY` (and optionally `LANGSMITH_PROJECT`) in the server's `.env`.

`LANGSMITH_TRACING` and the other generic tracing variables must stay unset or false: `src/cta/api/checks.py` makes the API refuse to start if they are on. Tracing is switched on inside the process, only after the personal-data scrub and every guardrail.

### 6.4 Exact new wording for "What is saved?"

Files: `web/lib/notice.ts` (the strings), the sentences-versus-code tests in `tests/test_requestlog.py` and `tests/test_tracing.py` (they pin the claims; they change in the same commit), `README.md` ("Safety and cost controls") and `docs/known-limits.md` item 19. Three changes:

1. **Replace** the landing line `NOTICE_SHORT` with:

> Your questions and the answers are saved, and also sent to LangSmith (a tracing service), to improve this assistant. Emails, phone numbers, ID numbers and names are removed first, where we can detect them. Please don't type personal information.

2. **Replace** the bullet beginning "Optional developer tracing is off by default..." with:

> Each question you ask (after emails, phone numbers, ID numbers and detectable names are removed) and the assistant's reply are also sent to LangSmith, a third-party tracing service, with the steps taken and token counts, so mistakes can be found and fixed. LangSmith keeps them for 14 days. No IP address and no cookies are sent.

3. **Add** one bullet, because the hosting providers see addresses:

> The page is hosted on Vercel and the assistant runs on Amazon Web Services. They may keep ordinary technical logs, such as network addresses, under their own policies. This project does not save them.

Two other bullets already match the code and stay: "No IP address and no cookies are stored" (our database and app) and the in-memory counting sentence. The "30 days ... deleted by a clean-up command that is run by hand for now" bullet must change once the purge cron exists (7.4): "Older ones are deleted automatically every day." Retention figure 14 days is the plan's base retention; the owner confirms the workspace setting (step 8), and the sentence is changed if it differs.

---

## 7. Safety and operations

### 7.1 AWS budget alert

AWS Budgets: "monitor and receive notifications on your budgets free of charge"; threshold alerts are free; only action-enabled budgets beyond the first two cost $0.10 a day, and reports cost $0.01 each. https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/ . Create one **cost budget of $5 a month** (it also counts as one of the credit activities) with email alerts at 50 %, 80 % and 100 % of actual and 100 % forecast. Do not create budget actions or reports. On the Free plan nothing should be billed, so the alert's job is to show unexpected credit burn; the **credit balance** on the Billing console home is the real gauge: look at it daily in week 1, then weekly. A budget alert is not a stop; it is an email.

### 7.2 Kill switch: how to take the site down fast

Fastest first. Each one is independent of the others.

| Method | Effect | Time | Notes |
|---|---|---|---|
| `touch data/api_disabled` on the server (the file the Guard already checks, `DISABLED_FILE`) | Every `/ask` answers "The assistant is switched off for now. Please check back later." No model call. Remove the file to switch on. | seconds, no restart | `data/` must be a bind mount so the host can create the file; test it |
| `CTA_API_DISABLED=1` in `.env`, restart the API container | same reply | under a minute | the config path |
| Revoke the project's OpenAI key (dashboard) | the API cannot reach the model; costs stop at once | seconds | the page shows errors, not the polite message |
| Stop the Lightsail instance (console, **Stop**) | everything stops, Vercel returns an error for `/api/*` | under a minute | the plan is probably still billed while stopped (**unverified**); the attached static IP keeps its address |
| Take the link out of the README and set the Vercel project to a maintenance deployment | stops visitors | minutes | I did not read Vercel's rollback or pause docs: **unconfirmed** |

Use the first; practise it on the test day and write down how long it takes.

### 7.3 Database backup and restore

What can be rebuilt from `data/` (on the owner's machine, **not in git**):
- `chunks` (619 rows) and `calendar_events` (136): `uv run python -m cta.index.db migrate`, then `uv run python -m cta.index.load --yes`, then `uv run python -m cta.index.load_calendar --yes` (`docs/running.md`). The embeddings cost: about 136,000 tokens, roughly **$0.003** (`docs/running.md`), so a full re-embed is cheap. Measured: `data/processed/chunks.jsonl` is 964 kB.
- Not rebuildable: `request_logs` (the questions and answers of real visitors, plus the thumbs votes) and `eval_runs`.
- The data itself (`data/processed`, `data/calendar`, `data/pdfs`) exists only on the owner's laptop and in no repository: **keep a copy** (a tarball of the folders, about 20 MB with the PDFs; `data/raw` is 11 MB and `data/cache` 12 MB, neither needed to run).

Plan:
1. Nightly `pg_dump -Fc` inside the DB container to a dump file on the instance, keep 7 (5.5 MB each, measured), run by cron on the server.
2. Weekly: the owner copies the newest dump to the laptop (`scp`, nothing secret in it except visitors' redacted questions).
3. A Lightsail snapshot is not used: snapshots are off and billed separately (**unverified**), so the owner's own `pg_dump` index dump is the backup.
4. Restore drill on the test day: a throwaway container, `pg_restore`, compare row counts. A disaster restore is: new instance, compose up, `migrate`, `pg_restore` (or the three load commands if no dump survives, losing only the logs).

### 7.4 Log disk growth

- Postgres `request_logs`: about 2.2 KB a request (measured), about 7 MB at 100 a day with the 30-day purge. Run `python -m cta.api.purge --days 30` from cron every day (today it is run by hand; the notice then changes, 6.4).
- Docker container logs: "Log rotation is not enabled by default. The `max-size` option defaults to -1 (unlimited)". Set `max-size: "10m"` and `max-file: "3"` for every service. https://docs.docker.com/engine/logging/drivers/json-file/ (that page shows the Docker daemon form; the Compose form is **unconfirmed** from that page, so check it when writing the compose file). Uvicorn's access log is already off in the code; Caddy's stays off.
- Watch `df -h` on the test day and after a week; the 20 GB disk has a lot of room.

### 7.5 Secrets on the server

- Secrets: `OPENAI_API_KEY` (the project key), `POSTGRES_PASSWORD`, `LANGSMITH_API_KEY`, the DuckDNS token, and the shared header secret (also stored in the Vercel project settings).
- They live only in a `.env` file on the server, created by the owner by typing it on the server (an editor over SSH), mode 600. `.env` is git-ignored (checked: `git check-ignore .env` matches). **Never paste a value into this chat, a ticket, a screenshot or a commit.** When reporting back, say "set" or "not set", never the value.
- Rotate on suspicion: OpenAI key (revoke in the dashboard, new key, edit `.env`, restart), LangSmith key, DuckDNS token, the header secret (change both ends: Vercel accepts old and new during the swap, per the Vercel page).
- Network: the Lightsail firewall allows 80 and 443 (443 on IPv4 only) from anywhere and, once setup is finished, **22 only from your address** (the browser terminal then needs the Lightsail browser SSH option kept on, or your own SSH client with the downloaded key); Postgres stays bound to `127.0.0.1` (as in `docker-compose.yml`) and the API container is not published to the host at all; only Caddy is. SSH key login only, no password login; automatic security updates on. (These are my standard recommendations, not something I verified on an official page today.)

### 7.6 Launch-day check of the safety numbers

From `docs/decisions.md` ("Pre-launch checklist" and "Post-freeze safety fix"). Do this the day the link goes public, and again if the code changes, then record the result and date in `docs/decisions.md`:

| Number | Where it is in the code | Source to compare with |
|---|---|---|
| National Domestic Violence Hotline 1-800-799-7233 (SAFE), text START to 88788 | `danger` reply in `src/cta/api/screen.py` | thehotline.org (checked Oct 16 "as given", not re-fetched) |
| NYC 24-hour hotline 1-800-621-4673 (HOPE) | same | nyc.gov/site/hra/help/domestic-violence-support.page (not re-fetched) |
| City Tech Public Safety (718) 260-5550; campus phone 5550; emergency 5555 | same; **the page URL was never recorded** | the owner finds the City Tech Public Safety page and records its URL this time |
| 988 and 911 | Tier 1 reply in `screen.py` | the 988 Lifeline site; record the URL used |

Report back only "matches" or "differs: <number>"; I update the constants and the pinned test text if one differs. Also confirm the two hotline pages still load. This is the last blocker listed in `docs/polish-triage.md` (G1-2).

---

## 8. What only the owner can do by hand, in order

Never send me a key, token, password or the contents of `.env`. Each report-back is plain text.

| # | Step | Minutes | Report back |
|---|---|---|---|
| 1 | **Decide**: AWS first (this plan), and whether a $0.92-a-month domain is acceptable if DuckDNS fails; decide fail open or closed on the spend counter (5.3) | 10 | Your three answers |
| 2 | **AWS account.** Create a new account at aws.amazon.com/free and choose the **Free account plan**. Do not join AWS Organizations. | 15 | Did signup ask for a card (yes/no)? Plan shown on the Billing home? Credit balance shown ($)? The plan end date shown? |
| 3 | **AWS Budget.** Billing -> Budgets: a $5 monthly cost budget, email alerts at 50 %, 80 %, 100 % actual and 100 % forecast, no actions, no reports. Then open the Explore AWS widget and note the dollar value shown next to each activity. | 10 | Budget created (yes/no); the credit amount each activity shows; the balance after |
| 4 | **Lightsail instance** (done: `cta-server`, Ubuntu 24.04, $12 plan, Ohio us-east-2a, static IP `cta-ip`). Confirm the static IP is attached and the firewall rules (HTTP 80, SSH 22, HTTPS 443 IPv4 only), snapshots off. Next day, open Billing and Credits. | 15, plus 5 next day | Static IP attached, the three rules as shown, snapshots off; **whether the credit balance fell and the Lightsail charge was offset by credits**; whether any card was charged |
| 5 | **DuckDNS name.** Sign in with a provider, create a name, set the IPv4 address to `3.135.33.79`, leave IPv6 empty. The token is a secret. Check from the browser terminal that the name resolves to `3.135.33.79` before Caddy starts. | 10 | The name you chose (public, not the token); whether any limit or terms page notice appeared |
| 6 | **OpenAI project.** New project for this deployment with its own key; Limits: monthly spend limit **$7**, "Enforce a hard limit" on, alerts at $3 and $5. Optional but recommended: on a throwaway test project set a hard limit of $0.01 and make one tiny call, to see the `429 project_spend_limit_exceeded`. | 15, +10 for the optional test | The limit page text for the project (limit, whether the hard-limit toggle exists and is on); optionally what the test call returned (the error code only) |
| 7 | **LangSmith.** Create a free account and workspace; **do not add a card**; create an API key (a secret). Open Settings -> Billing and Usage -> Usage limits and the Usage page. | 15 | What the usage-limits page says for a no-card account; the trace limit and retention shown for the workspace |
| 8 | **Vercel.** Hobby account (GitHub login); import `medrees-1000/city-tech-assistant` with root directory `web`; add the environment variables `API_URL` and the header secret in the project settings; deploy. | 20 | The `vercel.app` address (public); the plan name shown; whether a change of `API_URL` needed a redeploy |
| 9 | **Type `.env` on the server** over SSH (the build session gives the exact list of names; you type the values). | 10 | "set" for each name; never values |
| 10 | **Test day** (section 10) with a friend or two. | 120 | The test-day result sheet |
| 11 | **Launch-day check** of the numbers (7.6), then the README refresh (screenshots, counts, link) | 30 | "matches" / "differs", then the commit |

Total about 4 hours of hands-on time, spread over two or three days; steps 2 to 4 are the only ones with a time limit (the 6-month clock starts at step 2, so do them close to the test day).

---

## 9. Risks, rollback, test day

### 9.1 The three biggest risks

1. **The rate limiter sees the proxy, not the visitor** (4.2). If missed, either all visitors share 10 questions a minute (the site looks broken), or a wrong trust setting lets anyone fake an address and skip the per-visitor limit. Mitigation: the secret header, forwarded-for from `X-Real-IP`, trusted-proxy setting limited to the Caddy network, and the test-day check from two different networks.
2. **A hard end date and an uncertain exit.** The AWS Free plan closes at 6 months or when credits run out, whichever is first, with data kept 90 days; the credits cover the burn ($72 for 6 months against a $100 signup credit) only if they apply to Lightsail (unconfirmed); Free plan accounts are for evaluation and "should not be used for processing sensitive data"; and the Hetzner fallback may not be orderable (CX23 shows unavailable), with CPX22 at EUR 19.49. Mitigation: the credit balance check in week 1, backups off the box, and the README line (3).
3. **Money and privacy rest on controls I could not fully verify.** Spend: the app has a $1 daily cap but no monthly cap (about $30), and the OpenAI hard limit is contested by one community report. Privacy: scrubbed questions now go to a third party (LangSmith), names written in unusual ways are not removed (known-limits 21), and the hosts keep their own logs. Mitigation: the app-side monthly and daily caps, the OpenAI test in step 6, the new notice wording (6.4) before the link is public.

Other, smaller: a single small server with no failover; Vercel Hobby is non-commercial only; an unmeasured peak memory per request; per-request timeout through the Vercel rewrite is unconfirmed; the data (`data/processed`) exists only on your laptop.

### 9.2 Rollback

- **Stop everything now:** kill switch file (7.2), then stop the Lightsail instance.
- **Bad deployment of the page:** redeploy the previous Git commit on Vercel (the exact UI is unconfirmed; the Git route always works) or remove the rewrite and deploy a closed notice.
- **Bad deployment on the server:** keep the previous image tag, `docker compose` back to it; the database schema only moves forward with `migrate`, so take a dump before every deploy.
- **Remove the link from the README** whenever the site is down or ended (3).
- **Costs out of control:** revoke the OpenAI key first, then stop the instance.

### 9.3 Test-day plan (owner and one or two friends; the link does not go in the README until it passes)

Before: a fresh dump; the caps temporarily low through the environment variables (daily request cap 15, daily spend cap 0.02) so the cap replies can be seen; LangSmith project set to a test name.

| # | Check | Pass when |
|---|---|---|
| 1 | Ask 20 questions of every route (calendar, chain, abstain with contact, distress reply, non-English, injection) on the real address, on desktop and on a phone on mobile data | answers match local behaviour; sources show; no browser console error or mixed-content warning |
| 2 | The owner and a friend on **different networks** ask 12 questions in a minute each | the 11th question of each person is refused with the rate-limit message, the other person is **not** affected |
| 3 | Check `/health` on the server over SSH | `blocked.rate_limited` counts it; the visitor's address appears in no log, `docker compose logs`, Caddy file or database row (grep for the two test addresses) |
| 4 | Try the origin directly, without the secret header, and a fake `X-Forwarded-For` | 403 from Caddy |
| 5 | Hit the low daily request cap and spend cap | the fixed replies appear, no OpenAI cost after the cap, `/health` shows it |
| 6 | Kill switch drill: create `data/api_disabled`, ask, remove it, ask; time it | polite message, then service restored; the time is written in this file |
| 7 | The slowest question you know (p95 was 10.3 s) through the Vercel path | answer returns, no gateway timeout |
| 8 | OpenAI dashboard cost against `/health.spend_today_usd` | within about 10 % (embedding calls may differ); the hard limit confirmed in step 6 |
| 9 | LangSmith | one trace per served question, none for blocked ones, no email, phone or ID in any payload, project retention shows 14 days; lower the limit and check that the assistant still answers when tracing fails |
| 10 | Memory and disk | `docker stats` peak during check 1, `df -h` |
| 11 | Backup and restore drill (7.3); certificate shows valid on the DuckDNS name | restored row counts equal; browser shows a valid certificate; Caddy renewal log line seen later in the week |
| 12 | AWS credit balance before and after the day | the daily burn matches about $0.40; the Lightsail charge is offset by credits and no card is charged |
| 13 | A friend uses the thumbs buttons and reads the "What is saved?" text | the votes are saved; the text matches the code and mentions LangSmith and the hosts |

After a pass: set the caps back to the 5.3 values, run the launch-day number check (7.6), update the README, push, and put the link in.

---

## 10. Unconfirmed list (everything I could not settle from an official page)

- Whether AWS asks for a card at signup (FAQ: "may" be requested).
- The dollar value of each AWS credit activity, and which of the two stated credit expiry rules applies.
- Whether the AWS free-plan credits pay for Lightsail at all (expected to be settled by Billing and Credits), whether AWS Budgets counts Lightsail, and whether stopped instances and snapshots are billed.
- The $12 plan's contents (2 GB, 2 vCPUs, 60 GB, 3 TB) and the absence of a separate IPv4 or disk charge: from the owner's console, not an official page; the single firewall table versus the two firewalls the guide describes.
- The Lightsail console wording (browser SSH option on the SSH rule, key download, Snapshots tab).
- Resizing a Lightsail instance (not read).
- Lightsail on the Free plan (the only statement is about a trial on the Paid plan).
- Hetzner: whether CX23 or CAX11 can be ordered now; the VAT that applies to the owner; the price page itself showed blanks and "unavailable".
- Cloudflare Registrar's `.com` price (Porkbun's $11.08 is confirmed).
- DuckDNS: number of free names, uptime, terms (its FAQ page returned 404).
- Whether Let's Encrypt issues certificates for `compute-1.amazonaws.com` names.
- Vercel: timeout for a rewrite to an external origin, whether `API_URL` is read at build time, whether the `vercel.json` header transform works with `next.config.mjs` rewrites, and the exact rollback/pause screens.
- Uvicorn defaults for `--proxy-headers` and `--forwarded-allow-ips`.
- OpenAI: whether the project-level hard limit is truly enforced (the official page says yes; one unread community post says no).
- LangSmith: what happens to traces past 5,000 with no card, and exactly how a "trace" is counted for the bill.
- Docker Compose syntax for log rotation (only the daemon form was on the page I read).
- Current hotline, Public Safety, 988 and 911 numbers (launch-day check; the Public Safety page URL was never recorded).
- Per-request peak memory and the Docker image sizes (not measured: no model call and no build were allowed).
