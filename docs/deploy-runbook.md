# Deploy runbook (Oct 18, 2026)

Source of truth for the plan and the prices: [docs/deployment-plan.md](deployment-plan.md). This file is the order of work. Every step says who does it: **owner** (accounts, cards, console clicks, anything with a secret) or **Claude Code** (commands and files, with the owner watching). Minutes are estimates.

Rules that hold for every step:
- No secret ever goes into the repo, a chat, a ticket, a screenshot or Vercel (except the one shared header secret, which the page needs, step 22). The OpenAI key lives only in `.env.production` on the server.
- When you report back, say "set" or "done", never a value.
- Nothing in Part A touched AWS, Vercel, OpenAI, LangSmith or DuckDNS. Everything below has been rehearsed locally on the laptop (docs/decisions.md, "Part A rehearsal"; the production stack, the restore and the smoke test ran against a local Caddy, and the page proxy ran with `next start`).

Paths used below (on the server, user `ubuntu`): the code is in `~/city-tech-assistant`; every compose command is run from there. Define once per login:

```bash
cd ~/city-tech-assistant
export COMPOSE_ARGS="--env-file .env.production -f docker-compose.prod.yml"
alias dc='docker compose $COMPOSE_ARGS'
```

## A. Accounts and the server

| # | Who | Min | Step |
|---|---|---|---|
| 1 | owner | 15 | **AWS account**, Free account plan (not Paid), no AWS Organizations. Note the plan end date and the credit balance shown on the Billing home. Report: card asked (yes/no), balance, end date. |
| 2 | owner | 10 | **AWS Budget alert** (also one of the credit activities): Billing, Budgets, cost budget of $5 a month, email alerts at 50 %, 80 % and 100 % actual and 100 % forecast, no actions, no reports (those cost money). Report: created (yes/no). |
| 3 | owner | 30 | **Launch the instance**: EC2, region us-east-1, name `cta`. AMI: Ubuntu Server LTS (the newest "Free tier eligible" one; Docker supports Ubuntu 22.04, 24.04 and 26.04 LTS, docs.docker.com/engine/install/ubuntu/, read 2026-10-18). Type `t3.small` (2 vCPU, 2 GiB). Key pair: new, download the `.pem` and keep it private; on your computer run `chmod 400 cta.pem` (AWS: "chmod 400" before the first SSH connection, docs.aws.amazon.com/AWSEC2/latest/UserGuide/connection-prereqs-general.html, read 2026-10-18 through a search summary). Network: a security group with exactly three inbound rules: **SSH (22) from My IP only** (AWS warns to authorize only your own address for port 22, docs.aws.amazon.com/AWSEC2/latest/UserGuide/changing-security-group.html, read 2026-10-18), **HTTP (80)** and **HTTPS (443)** from anywhere (Caddy needs 80 for the certificate); rule changes apply at once. No `ufw` is used: the security group is the firewall, and Postgres and the API have no published port. Storage: 20 GiB gp3. Advanced details, CPU credits: **Standard**. Then **Elastic IPs, Allocate Elastic IP address**, then **Actions, Associate Elastic IP address**, resource type Instance (same AWS page family, docs.aws.amazon.com/AWSEC2/latest/UserGuide/working-with-eips.html, read 2026-10-18; it also says an Elastic IP is charged whether in use or idle, so release it if you ever delete the instance). Report: instance type, region; next day the Cost Explorer lines for EC2, IPv4 and EBS and whether the credit balance fell by that amount. |
| 4 | owner | 5 | **SSH in**: `ssh -i cta.pem ubuntu@<elastic-ip>` (format `ssh -i key.pem user@host` from docs.aws.amazon.com/AWSEC2/latest/UserGuide/connect-linux-inst-ssh.html, read 2026-10-18; `ubuntu` as the Ubuntu user name is **unverified** here: the page defers to another one). Check that password login is off: `sudo sshd -T \| grep -i passwordauthentication` (`sshd -T` "prints the effective configuration", man.openbsd.org/sshd.8, read 2026-10-18; the keyword defaults to `yes` when nothing sets it, man.openbsd.org/sshd_config). It must print `passwordauthentication no`. If it prints `yes`: `echo 'PasswordAuthentication no' \| sudo tee /etc/ssh/sshd_config.d/00-cta.conf && sudo sshd -t && sudo systemctl reload ssh`. The file name starts with `00-` because, per sshd_config, `Include` files are read in lexical order and "the first obtained value will be used"; the exact interplay with the Ubuntu image's own files is **unverified**, so re-run the check after the change. Report: the printed word. |
| 5 | Claude Code | 5 | **2 GB swap file**: `sudo dd if=/dev/zero of=/swapfile bs=1M count=2048 status=progress && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile && echo '/swapfile none swap defaults 0 0' \| sudo tee -a /etc/fstab && echo 'vm.swappiness=10' \| sudo tee /etc/sysctl.d/99-cta.conf && sudo sysctl --system`. Sources (read 2026-10-18): swapon(8), man7.org/linux/man-pages/man8/swapon.8.html ("The most portable solution to create a swap file is to use dd(1) and /dev/zero"; files made with cp/truncate have holes and are rejected, and `fallocate` ones may be too, so `dd` is used here; the fstab fields are source, `none`, `swap`, options with `defaults` as the convention; `swapon --show` lists swap areas); sysctl(8), man7.org/linux/man-pages/man8/sysctl.8.html (`--system` loads `/etc/sysctl.d/*.conf`); the kernel's vm.swappiness is a value from 0 to 200, default 60, and lower values make swapping less likely (kernel.org/doc/html/latest/admin-guide/sysctl/vm.html). **Unverified** on an official page: `chmod 600 /swapfile` (the man pages I read do not mention it; AWS's swap article returned 403) and `status=progress`. Check: `swapon --show` and `free -h` show 2 GiB. |
| 6 | Claude Code | 5 | **Automatic security updates**: Ubuntu installs `unattended-upgrades` by default; if it is missing `sudo apt install unattended-upgrades`. Make sure `/etc/apt/apt.conf.d/20auto-upgrades` holds exactly `APT::Periodic::Update-Package-Lists "1";` and `APT::Periodic::Unattended-Upgrade "1";` (`1` runs daily): `printf 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n' \| sudo tee /etc/apt/apt.conf.d/20auto-upgrades`. Check with `sudo unattended-upgrade -v --dry-run`; logs are in `/var/log/unattended-upgrades`. Source: ubuntu.com/server/docs/how-to/software/automatic-updates/ (read 2026-10-18). The earlier `dpkg-reconfigure` command is not on that page and was removed. |
| 7 | Claude Code | 10 | **Install Docker Engine from Docker's apt repository**: run the block under this table (docs.docker.com/engine/install/ubuntu/, "Install using the apt repository", read 2026-10-18), which ends with the post-install lines from docs.docker.com/engine/install/linux-postinstall/ (read 2026-10-18). Check: `docker compose version`. **Unverified:** `docker run --rm hello-world` as the check (the page I fetched did not show it). |
| 8 | owner | 10 | **DuckDNS name**: sign in at duckdns.org with a provider, create a name, set its address to the Elastic IP in the web form, keep the token private. The update call, if you ever need it from a shell, is `https://www.duckdns.org/update?domains=<name>&token=<token>&ip=<elastic-ip>`; it answers `OK` or `KO`, and the page recommends HTTPS (www.duckdns.org/spec.jsp, read 2026-10-18; it states no rate limit). Do not put the token in a command you paste anywhere: `read -rs DUCK; curl -s "https://www.duckdns.org/update?domains=<name>&token=$DUCK&ip=<elastic-ip>"; unset DUCK`. Check from the server: `getent hosts <name>.duckdns.org` prints the Elastic IP (**unverified** against an official page; any DNS lookup works, for example `dig +short`). Report: the name (public), nothing else. |

Docker install block (step 7), copied from the two pages above on 2026-10-18; the install page now uses the `.sources` format, not the old `.list` line:

```bash
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
# post-install (linux-postinstall page): non-root use, and start on boot
sudo groupadd docker          # the group may already exist
sudo usermod -aG docker $USER # then log out and in, or run: newgrp docker
sudo systemctl enable docker.service
sudo systemctl enable containerd.service
```

## B. Keys and files

| # | Who | Min | Step |
|---|---|---|---|
| 9 | owner | 15 | **A NEW OpenAI project for production**: platform.openai.com, create a project (for example `city-tech-assistant-prod`), create **a new API key inside it** (not the development key), Limits: monthly spend limit **$7** with **"Enforce a hard limit" on**, alerts at $3 and $5. Do not copy the key anywhere yet. Report: limit page shows $7 and hard limit on (yes/no). |
| 10 | Claude Code | 5 | **Get the code on the server**: `git clone https://github.com/medrees-1000/city-tech-assistant.git && cd city-tech-assistant && mkdir -p backups`. |
| 11 | owner | 10 | **Copy the collected data and the index dump from the laptop** (the data is not in git; `data/calendar` comes with the clone, `data/processed` does not): `rsync -av data/processed/ ubuntu@<name>.duckdns.org:city-tech-assistant/data/processed/` and `scp backups/index-2026-10-18.dump ubuntu@<name>.duckdns.org:city-tech-assistant/backups/` (SSH needs `-i cta.pem`; if SSH to the DuckDNS name is blocked use the Elastic IP). Check on the server: `ls data/processed/courses \| head -3`. (`rsync` and `scp` usage here is **unverified** against an official page.) |
| 12 | owner | 15 | **Create `.env.production` on the server, typing the secrets there** (never pasted into chat): `cp .env.production.example .env.production && chmod 600 .env.production && nano .env.production`. Fill: `POSTGRES_PASSWORD` (`openssl rand -hex 16` in another terminal; the stack builds a URL from it, so keep it hex), `OPENAI_API_KEY` (the new project key from step 9), `CTA_HOSTNAME` (`<name>.duckdns.org`), `CTA_TRACING_ENABLED=true`, `CTA_TRACING=on`, `LANGSMITH_API_KEY` and `LANGSMITH_PROJECT=city-tech-assistant` (after step 20), and leave the rest empty (the caps in `config/models.yaml` apply). |
| 13 | Claude Code | 2 | **Generate the two proxy secrets without printing them** (`openssl rand -hex 32`: `-hex` "shows the output as a hex string", docs.openssl.org/master/man1/openssl-rand/, read 2026-10-18): `printf 'CTA_PROXY_SECRET=%s\nCTA_IP_SALT=%s\n' "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" >> .env.production`, then remove the two empty lines of the same names that the example has (`nano`). `grep -c '^CTA_PROXY_SECRET=.\{64\}' .env.production` must print 1. |
| 14 | Claude Code | 2 | **Stamp the commit** the image is built from: `sed -i "s/^CTA_COMMIT=.*/CTA_COMMIT=$(git rev-parse --short HEAD)/" .env.production`. |

## C. Start, restore, check

| # | Who | Min | Step |
|---|---|---|---|
| 15 | Claude Code | 10 | **Start the stack**: `dc up -d --build`. Wait for `dc ps` to show `db`, `api` healthy, `migrate` exited 0, `purge` and `caddy` up. Caddy gets its certificate for the DuckDNS name by itself (needs ports 80 and 443 open and the name resolving, steps 3 and 8). If Caddy cannot get one, `dc logs caddy` says why (the log lines hold no secret or address). |
| 16 | Claude Code | 3 | **Restore the index** (no re-embedding): `scripts/restore_index.sh backups/index-2026-10-18.dump`. It prints the counts: expect `before: chunks=0 calendar_events=0 request_logs=0` and `after:  chunks=619 calendar_events=136 request_logs=0`. The dump holds only those two tables; request logs are never exported or restored. |
| 17 | Claude Code | 3 | **Look at the health body from inside** (it is not public): `dc exec api python -c "import urllib.request,json;print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:8000/health')),indent=1))"`. Expect `status ok`, `version` = the commit, `settings.tracing true`, `settings.rescue on`, `monthly_cap_usd 5.0`, `proxy_required true`. |
| 18 | Claude Code | 5 | **Smoke test the public HTTPS name** (from the laptop; about $0.002): `uv run python scripts/smoke_live.py https://<name>.duckdns.org --secret "$CTA_PROXY_SECRET" --health hidden` (put the secret in the laptop's shell for this one command; do not echo it). Expect 9 passed, 0 failed. |
| 19 | owner | 10 | **Backup copy**: the restored dump is the first backup. Keep it in two places: the laptop (`~/city-tech-assistant/backups/`, git-ignored) and the server (`~/city-tech-assistant/backups/`). The file holds only public City Tech text and its embeddings (4.5 MB), no student data, so a private cloud drive is also fine. After any change to the data, make a new one: `COMPOSE_ARGS="$COMPOSE_ARGS" scripts/export_index.sh backups/index-$(date +%F).dump`. |

## D. LangSmith and Vercel

| # | Who | Min | Step |
|---|---|---|---|
| 20 | owner | 15 | **LangSmith**: free Developer account and workspace, **no card** (without a card the plan is limited to 5,000 traces a month; langchain.com/pricing and docs.langchain.com/langsmith/billing, read 2026-10-18). Create an API key (a secret: type it into `.env.production` on the server, step 12, then `dc up -d api`). Open Settings, Billing and Usage, Usage limits, and note what it shows for a workspace with no card. Report: the trace limit and the retention shown (the page text says 14 days). |
| 21 | Claude Code | 3 | **Check one trace** after one real question: LangSmith shows exactly one trace named `ask` with tags `route:...` and metadata `commit`, `config_version`, `rescue`, `cost_usd`, `latency_ms`; its input holds the scrubbed question, never an email, phone or ID. Ask "I want to kill myself" as well: **no trace** must appear for it. |
| 22 | owner | 20 | **Vercel project**: Hobby plan (free, non-commercial; vercel.com/docs/plans/hobby), sign in with GitHub, import `medrees-1000/city-tech-assistant`, **Root Directory `web`**, framework Next.js (`web/vercel.json` says so). Environment variables, **Production only** (names in `web/.env.example`): `API_URL=https://<name>.duckdns.org` and `CTA_PROXY_SECRET=<the same value as on the server>` (read it once on the server: `grep '^CTA_PROXY_SECRET=' .env.production \| cut -d= -f2`, paste it into Vercel, clear the terminal). Deploy. Open the production `*.vercel.app` address in a private window; if it asks for a Vercel login, turn off Deployment Protection for production (the setting names changed over time: unconfirmed). Report: the address (public), the plan name shown. |
| 23 | Claude Code | 5 | **Smoke test the real page path** (the Vercel rewrite): `uv run python scripts/smoke_live.py https://<project>.vercel.app --prefix /api --health hidden` (no secret: the page's proxy adds it). Expect 9 passed. Also: `curl -s -o /dev/null -w '%{http_code}' https://<project>.vercel.app/api/health` must print 404, and the same against `https://<name>.duckdns.org/ask` without the secret header must print 403. |
| 24 | owner | 10 | **Two-network test of the visitor address** (the check that the limiter sees real visitors, not the proxy): run step 23's command on the home Wi-Fi, then right away (within the same minute) from a phone hotspot or a friend's network. Both runs must pass 9 of 9. Then run it again on the first network within a minute: now it must **fail** early with "rate limited" answers (same visitor, 10 a minute). If the second network also fails on the first run, the API is seeing one address for everyone: stop and report. Report: pass / fail of the three runs. |
| 25 | owner | 10 | **Optional uptime check**: a free uptime monitor (for example UptimeRobot) on the Vercel page's `/` (the API's `/health` is deliberately not public). I did not read any monitor's terms or limits: unconfirmed. An alert tells you the page or Vercel is down, not the API; the smoke script is the API check. |

## E. Test day, launch, shutdown

| # | Who | Min | Step |
|---|---|---|---|
| 26 | owner + Claude Code | 120 | **Test day** (the link is not in the README until it passes). Use `docs/deployment-plan.md` section 9.3 and add: (a) ask 20 questions from desktop and a phone on mobile data; (b) kill-switch drill, with timing: `touch ~/city-tech-assistant/data/api_disabled`, ask an ordinary question on the page, see "The assistant is temporarily paused. Please check back later." plus the crisis sentence, and check that "I want to kill myself" still gets the 988 reply, `rm` the file, ask again (write the seconds down); (c) cap drill: set `CTA_MONTHLY_SPEND_CAP_USD=0.0001` in `.env.production`, `dc up -d api`, ask a normal question (expect the paused-for-the-month reply with the Registrar and Advisement contacts) and "I want to kill myself" (expect the 988 reply), then empty the variable and `dc up -d api`; (d) `docker stats --no-stream` during the 20 questions: if the API stays under about 400 MB, `t3.micro` is an option for the credits; (e) a restore drill into a scratch database: `dc exec db createdb -U cta cta_scratch` (`createdb -U` is **unverified**: the page I read covers `dropdb`), then `dc exec api sh -c 'DATABASE_URL=$(echo "$DATABASE_URL" | sed "s#/cta\$#/cta_scratch#") python -m cta.index.db migrate'`, then `CTA_DB=cta_scratch scripts/restore_index.sh backups/index-2026-10-18.dump` (expect `after:  chunks=619 calendar_events=136`), then `dc exec db dropdb -U cta cta_scratch` (`dropdb -U` verified, postgresql.org/docs/17/app-dropdb.html, read 2026-10-18); (f) look at `dc logs` for any address or secret (none expected); (g) AWS credit balance before and after the day (the burn should be about $0.67 a day); (h) LangSmith shows the traces and none for the safety questions; (i) the page's "What is saved?" text matches what you saw. |
| 27 | owner | 30 | **Launch-day re-check of the safety numbers** (docs/decisions.md "Pre-launch checklist", docs/polish-triage.md G1-2). Compare each number in `src/cta/api/screen.py` with its source the same day: National Domestic Violence Hotline 1-800-799-7233 (SAFE), text START to 88788 (thehotline.org); NYC 24-hour hotline 1-800-621-4673 (HOPE) (nyc.gov/site/hra/help/domestic-violence-support.page); City Tech Public Safety (718) 260-5550, campus phone 5550, emergency 5555 (the City Tech Public Safety page: **record its URL this time**, it was never saved); 988 and 911 in the distress reply and in the crisis sentence that ends the kill-switch, daily-cap and monthly-cap replies (both are built from `LIFELINE` and `EMERGENCY` in `src/cta/api/screen.py`; 988lifeline.org). Report only "matches" or "differs: <number>". If one differs Claude Code changes the constant and the pinned test, and the rest waits. |
| 28 | Claude Code | 30 | **README refresh** after the test day passes (not done in Part A): the live link, the status line, screenshots, test counts, the cost and safety paragraphs (monthly cap, hashed address, the daily purge, tracing). Write the end date of the hosting (AWS signup date plus six months) next to the link. |
| 29 | owner | 15 | **A week before the AWS credits end** (they end at 6 months or when used up, whichever is first; the account then closes and AWS keeps the data 90 days, docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html): read the credit balance and decide: (A) upgrade to the Paid plan (about $20.51 a month at this size: section 1.3 of the plan); (B) move to Hetzner (confirm a CX23 can be ordered first; EUR 5.99 a month excluding VAT if it can; the same compose files and the dump restore apply); or (C) shut down. |
| 30 | Claude Code | 30 | **Shutdown or move** (after the choice): make a last `export_index.sh` dump and copy it to the laptop; for a move, repeat steps 3 to 18 on the new server and change `API_URL` in Vercel (a redeploy is not needed because the proxy reads it at run time; unconfirmed on Vercel, so redeploy if the old address is still used); for a shutdown, switch the kill switch on first, change the README line to "The live demo ended on <date> when the free hosting credits ran out. The recorded walkthrough is below." and remove the link the same day, then stop the instance (the account closes by itself), revoke the OpenAI project key, delete the LangSmith project (its traces expire after 14 days anyway) and delete the DuckDNS name. The Vercel project can be deleted or left: with no server it shows the friendly "can't reach the assistant" message. |

## Stop commands (the kill switch and what is above it)

Fastest first. Each works without the others.

| What | Command (on the server, in `~/city-tech-assistant`) | Effect | Back on |
|---|---|---|---|
| **Pause** (file kill switch, no restart, seconds) | `touch data/api_disabled` | every `/ask` answers "The assistant is temporarily paused. Please check back later." plus the crisis sentence (988, 911), with no model call, for every question except the regex safety ones (self-harm, danger, bereavement, personal numbers, off-topic, stress), which still get their normal fixed reply; the page shows it as a normal reply | `rm data/api_disabled` |
| Pause by environment (needs a restart of the API, about 20 s) | set `CTA_API_DISABLED=1` in `.env.production`, then `dc up -d api` | same | empty the variable, `dc up -d api` |
| Stop the API only | `dc stop api` | the page shows "I can't reach the assistant right now." | `dc start api` |
| Stop everything | `dc stop` (or `dc down`; never `dc down -v`, which deletes the database volume) | site down; Caddy and the database stopped | `dc up -d` |
| Cut off all spending at the source | revoke the production key in the OpenAI dashboard | model calls fail; the page shows "I couldn't get an answer just now." | create a new key, edit `.env.production`, `dc up -d api` |
| Stop the whole server | EC2 console, Stop instance | everything stops (the Elastic IP is still billed) | Start instance, then `dc up -d` if the stack does not start itself |

The monthly cap pauses the model on its own at $5 (UTC month, config `guardrails.monthly_spend_cap_usd`; `CTA_MONTHLY_SPEND_CAP_USD` overrides it); the OpenAI project limit of $7 is the backstop behind it.

## Which routes still answer at the monthly cap

Only the fixed replies of the regex safety screen, because they need no model call: distress (988 and 911), danger (Public Safety and the hotlines), bereavement, the personal-number refusal (Social Security number shapes), the fixed off-topic reply (prompt-injection phrases) and the stress reply. Everything that needs a model (the classifier, the calendar row choice, retrieval, a prerequisite chain, the language check for a non-English question) gets the "paused for the rest of this month" message with the Registrar and Advisement contacts. A non-English message that is about self-harm is therefore **not** caught at the cap (the screens run on an English translation, which needs a model call). Since Oct 18, 2026 the order in `/ask` is: rate limit, regex safety screen, kill switch, daily cap, monthly cap. So these replies are never replaced by a "paused" message, **including when the kill switch is on**: a 988 or danger message gets its normal reply, and every other question gets "temporarily paused" with the crisis line and no model call. `/health` works either way.

## Request-log retention today, and a proposal (nothing built)

Today: the production stack runs `python -m cta.api.purge --days 30` once a day (the `purge` service), which deletes API rows older than 30 days (never eval rows). What a row holds: the redacted question and answer, the route and its details (which pages were used, step times, tokens, cost), the thumbs vote if any; no address, no cookie. Rows for requests the safety screen handled hold **no question text** (only its length) and cost 0. LangSmith keeps traces 14 days on the free plan, separately.

Proposal: keep 30 days for normal rows (it is what the page promises and is enough to debug and read votes). One nuance to accept or fix: the monthly cap sums `request_logs` for the current UTC month, and the purge deletes rows after 30 days, so on the 31st of a 31-day month the 1st's rows may be gone, which can undercount by at most one day's cost (bounded by the $1 daily cap, in practice cents) against a $2 gap between the app cap ($5) and the OpenAI limit ($7). If that ever matters, a tiny non-sensitive `usage_daily` table (date, requests, cost) would remove it; I did not build it. Also worth deciding: whether the safety-screen rows (which store no text) may be kept longer than 30 days as counters. I would not: simpler to keep one rule.

Safety-screen requests and our logs, today: for the regex tiers (self-harm, danger, bereavement, personal numbers, off-topic) our own log stores **no question text**, the fixed reply, the reason, zero cost and the length of the question. They are never sent to LangSmith (a test proves it, including the two output nets, which now withhold the reply text). I propose **no change** to what our log stores for them: it is already the minimum that still lets `/health` and the log reader count them.

## Command verification (read 2026-10-18)

Every command above that is not plain shell was checked against an official page on 2026-10-18; where a page did not confirm it, the step says **unverified** and it is listed here. No code was changed for this check.

| Command or setting | Official source | Result |
|---|---|---|
| Docker Engine install on Ubuntu (apt repository, `.sources` file, packages incl. `docker-compose-plugin`) | https://docs.docker.com/engine/install/ubuntu/ | verified; supported: Ubuntu 22.04, 24.04, 26.04 LTS (and 26.10). The old `.list` line in the first draft was out of date and is replaced |
| `groupadd docker`, `usermod -aG docker $USER`, `newgrp docker`, `systemctl enable docker.service` / `containerd.service` | https://docs.docker.com/engine/install/linux-postinstall/ | verified |
| `docker compose` global `-f`, `--env-file`, `-p`; subcommands `up`, `exec`, `logs`, `ps`, `stop`, `start`, `down`, `run`, `config` | https://docs.docker.com/reference/cli/docker/compose/ | verified |
| `up -d`, `--build`, `--force-recreate`, `--wait` | https://docs.docker.com/reference/cli/docker/compose/up/ | verified |
| `exec -T` (no TTY; TTY is the default), `-e` | https://docs.docker.com/reference/cli/docker/compose/exec/ | verified |
| `down -v` removes named volumes (so the runbook says never to use it) | https://docs.docker.com/reference/cli/docker/compose/down/ | verified |
| `docker stats --no-stream`, the `MEM USAGE / LIMIT` column | https://docs.docker.com/reference/cli/docker/container/stats/ | verified |
| unattended-upgrades: `20auto-upgrades` contents, `unattended-upgrade -v --dry-run`, logs folder | https://ubuntu.com/server/docs/how-to/software/automatic-updates/ | verified; installed by default on Ubuntu |
| swap file: `dd` from `/dev/zero`, `mkswap`, `swapon`, the fstab swap line, `swapon --show` | https://man7.org/linux/man-pages/man8/swapon.8.html, https://man7.org/linux/man-pages/man8/mkswap.8.html | verified (the man pages recommend `dd`; `fallocate` files may be rejected) |
| `sysctl --system` and `/etc/sysctl.d/*.conf` | https://man7.org/linux/man-pages/man8/sysctl.8.html | verified |
| `vm.swappiness` range 0 to 200, default 60 | https://www.kernel.org/doc/html/latest/admin-guide/sysctl/vm.html | verified |
| `sshd -T` and `-t`; `PasswordAuthentication` default `yes`; `Include` order and "first obtained value" | https://man.openbsd.org/sshd.8, https://man.openbsd.org/sshd_config | verified (the Ubuntu image's own defaults are not covered: re-run the check) |
| SSH to EC2: `ssh -i key.pem user@host`; `chmod 400` on the key | https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/connect-linux-inst-ssh.html; the `chmod 400` rule through a search summary of connection-prereqs-general.html | verified / summary only |
| Elastic IP allocate and associate (console), charged while idle | https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/working-with-eips.html | verified |
| Security group rules (console), "My IP", port 22 warning, changes apply at once | https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/changing-security-group.html | verified |
| DuckDNS update URL, `OK`/`KO`, HTTPS recommended, no stated rate limit | https://www.duckdns.org/spec.jsp | verified |
| Caddyfile `{$VAR}` substitution, global options block first, `admin off`, global `log` block, `format filter` with `fields`, `>` nesting, `delete`, `wrap json`, bare-port site is plain HTTP, access log only with the `log` directive | https://caddyserver.com/docs/caddyfile/concepts, /options, /directives/log | verified (the page says a bare port has no hostname, so no automatic HTTPS; `:80` is not listed word for word) |
| `pg_dump --format=custom` (compressed), `-t`, `-U`; `--no-owner` is ignored for archive dumps (harmless) | https://www.postgresql.org/docs/17/app-pgdump.html | verified |
| `pg_restore --clean --if-exists --no-owner --exit-on-error`, `-t`, `--list`, reading the archive from standard input | https://www.postgresql.org/docs/17/app-pgrestore.html | verified (`-j` cannot read from a pipe: not used) |
| `psql -t -A -c -d -U`, `dropdb -U` / `--force` | https://www.postgresql.org/docs/17/app-psql.html, /app-dropdb.html | verified |
| `openssl rand -hex 32` | https://docs.openssl.org/master/man1/openssl-rand/ | verified |

**Unverified (no official page confirmed them; each is marked in its step):**
1. `chmod 600 /swapfile` and `dd ... status=progress` (the swapon and mkswap man pages do not mention them; AWS's swap article returned 403).
2. `createdb -U cta ...` in the restore drill (the page I read covers `dropdb`).
3. `docker run --rm hello-world` as the Docker check.
4. `systemctl status unattended-upgrades` (removed from the runbook; the dry-run command replaced it).
5. The default SSH user name `ubuntu` for Ubuntu AMIs (the AWS page defers to another page) and Ubuntu's default for password login (the check in step 4 handles it).
6. `getent hosts <name>` to test DNS (standard; `dig +short` is the alternative; no official page read).
7. `rsync -av` and `scp` in step 11 (standard OpenSSH/rsync usage; no man page read).
8. The Vercel dashboard steps in step 22 and the Deployment Protection setting names (Vercel's UI changes; the Hobby plan page was read in the plan, not these screens).
9. The AWS console launch settings in step 3 beyond security groups and Elastic IPs (AMI choice, CPU credit "Standard", gp3 size): the EC2 launch pages were not read.
10. `sudo sshd -t` before the reload (documented as `-t` test mode, but the order in this one-liner is mine).

## Contact for trouble

`dc logs --tail 100 api` (no address or secret appears in any log: a test and the rehearsal checked it), `dc ps`, and the health body from step 17.
