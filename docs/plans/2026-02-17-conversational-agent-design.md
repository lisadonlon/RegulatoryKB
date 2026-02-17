# Design: RegKB Conversational Regulatory Intelligence Agent

**Date**: 17 February 2026
**Author**: Lisa Donlon / Claude
**Status**: Approved

---

## Problem Statement

RegKB's intelligence pipeline has all the pieces (fetch, filter, analyze, summarize, email) but they're stitched together with manual CLI commands and a fragile NSSM service. The user experience is poor:

- Every action requires manual trigger
- NSSM service won't reliably start (wrong Python, SYSTEM account issues)
- Email digest is one-way (reply-download needs manual `regkb intel poll`)
- Web UI is basic server-rendered HTML with no real interactivity
- No automation — no scheduled runs, no push notifications
- Two Python installations (3.11 vs 3.13) causing confusion

## Solution

Rebuild the interaction model around a **Telegram bot as the primary interface**, backed by the existing pipeline. The bot becomes a regulatory assistant — it sends digests, takes commands, lets you approve/reject with inline buttons, and answers questions about the KB. Email stays for scheduled digests. Web dashboard becomes a read-only status/admin view.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary interface | Telegram bot | Free API, push notifications, inline keyboards, works on phone |
| Chat platform | Telegram (not WhatsApp) | Free bot API vs $0.05-0.08/conversation. User agreed to install |
| Telegram library | `python-telegram-bot` v21+ | Async, well-maintained, 60M+ downloads |
| Scheduler | APScheduler (in-process) | Replaces flaky NSSM + Task Scheduler combo |
| Webhook vs polling | Long-polling initially | No cloud endpoint needed to start |
| Command router | New module bridging all input channels | Telegram, email, and web all call same action functions |
| Process model | Single Python process | FastAPI + bot + scheduler in one process. One thing to manage |
| Python version | 3.11 (C:\Python311x64) | The one that actually works and is in PATH |
| Cloud stance | Hybrid | Core data local. Cloud for delivery channels (Telegram API, SMTP) |
| Budget | <$10/mo | Telegram free, Claude Haiku ~$1-3/mo, RSS feeds free |
| Data sources | Multi-source (IoI + direct RSS) | IoI for discovery/curation, direct feeds for PDF links |

## Architecture

```
+-----------------------------------------------------+
|                    USER (Lisa)                        |
|   Telegram  .  Email  .  Browser                     |
+------+----------------+--------------+--------------+
       |                |              |
       v                v              v
+-----------+  +--------------+  +--------------+
| Telegram  |  | IMAP Poller  |  | FastAPI Web  |
| Bot       |  | (email reply)|  | (admin/status|
| (python-  |  |              |  |  dashboard)  |
| telegram  |  |              |  |              |
| -bot)     |  |              |  |              |
+-----+-----+  +------+-------+  +------+-------+
      |                |                 |
      +----------------+-----------------+
                       v
          +------------------------+
          |   Command Router       |
          |   (unified action      |
          |    dispatcher)         |
          +------------------------+
                       v
      +------------------------------------+
      |       Existing Pipeline            |
      |  Fetcher -> Filter -> Analyzer ->  |
      |  Summarizer -> Emailer             |
      |  + DigestTracker, URLResolver,     |
      |    ReplyHandler, Downloader        |
      +------------------------------------+
                       v
      +------------------------------------+
      |       Data Layer                   |
      |  SQLite . ChromaDB . PDFs . .env   |
      +------------------------------------+
```

## Multi-Source Fetching

Keep Index-of-Indexes for discovery/curation. Add direct RSS/Atom feeds for PDF links.

Each source gets an adapter that outputs the same `NewsletterEntry` format. Pipeline deduplicates across sources before filtering.

| Source | Type | Content | Direct PDF? |
|--------|------|---------|-------------|
| Index-of-Indexes | CSV | Curated global regulatory updates | No (LinkedIn) |
| FDA CDRH | RSS | Device guidance, 510(k), recalls | Yes |
| EU Official Journal | Atom/RSS | Regulations, directives | Yes |
| MHRA | RSS | Guidance, safety alerts | Yes |
| TGA | RSS | Medical device alerts, guidance | Yes |
| Health Canada | RSS | Recalls, guidance | Yes |
| ISO News | RSS | Standards news | No (paid) |

## Telegram Bot Commands

| Command | Action |
|---------|--------|
| `/digest` | Run pipeline now, send results to chat |
| `/status` | Pipeline status, KB stats, next scheduled run |
| `/pending` | Show pending downloads with approve/reject buttons |
| `/search <query>` | Search KB, return top 3 results |
| `/fetch` | Fetch latest updates (no email) |
| `/help` | Command list |
| Natural language | "What's new from FDA?" -> filtered search |

Inline keyboard buttons for approve/reject/details on pending items.

Push notifications for critical alerts (MDR, IVDR, recall, safety alert).

Auth: restricted to Lisa's Telegram user ID only.

## Scheduled Jobs (APScheduler)

| Job | Schedule | Action |
|-----|----------|--------|
| Weekly digest | Monday 08:00 | Full pipeline -> email + Telegram |
| Daily alert | 09:00 | Check for critical items -> Telegram + email if found |
| IMAP poll | Every 30 min | Check for reply-to-download requests |
| Source health check | Daily 07:00 | Verify all source feeds are responding |

## Implementation Phases

### Phase 0: Foundation (Week 1, first half)

Fix what's broken before building new things.

- Consolidate to Python 3.11 (service uses same Python that works)
- Single-process architecture: FastAPI + APScheduler in one process
- Fix NSSM service: correct Python, test start/stop/restart
- Add `/health` endpoint: scheduler state, last run times, error count
- Structured logging: consistent JSON logging

**Exit criteria**: `nssm restart RegKBWeb` works. `/health` returns green. Scheduler fires on time.

### Phase 1: Telegram Bot (Week 1 second half -> Week 2)

The primary interface.

- Create bot via BotFather, get token
- Bot runner inside FastAPI process (`python-telegram-bot` v21 async)
- Core commands: `/digest`, `/status`, `/pending`, `/search`, `/help`
- Inline keyboards: approve/reject buttons, action buttons on digests
- Push notifications: critical alerts sent immediately
- Auth: restrict to Lisa's Telegram user ID

**Exit criteria**: `/digest` from phone returns formatted summary with action buttons.

### Phase 2: Automation (Week 2 -> Week 3)

It runs itself.

- APScheduler jobs: weekly digest, daily alert, IMAP poll
- Telegram delivery: scheduled digests go to email AND Telegram
- IMAP auto-poll: no more manual `regkb intel poll`
- Error recovery: failed jobs retry 3x with backoff, alert via Telegram
- Persistent job state: SQLite so restarts don't re-run completed jobs

**Exit criteria**: Do nothing for a week. Monday morning: digest on Telegram and email. Critical items alert immediately.

### Phase 3: Direct Source Adapters (Week 3 -> Week 4)

Better data, direct PDF links.

- Source adapter interface: base class with `fetch() -> list[NewsletterEntry]`
- FDA CDRH adapter (RSS, direct gov links)
- EU adapter (Official Journal + MDCG feeds)
- MHRA adapter (GOV.UK RSS)
- Cross-source dedup: same doc from IoI + FDA direct -> keep one with PDF link
- Source health monitoring: alert on feed failures

**Exit criteria**: Pipeline fetches from 4+ sources. Direct PDF links for FDA/EU/MHRA.

### Phase 4: Conversational Intelligence (Week 4, stretch)

Natural language interaction.

- KB search via Telegram: "What FDA cybersecurity guidance do we have?"
- Natural language commands: "Download that MDSAP doc" -> fuzzy match -> confirm
- Digest Q&A: reply to digest asking "tell me more about #3"
- Local LLM option: Nexa/Qwen on NPU for simple queries, Claude for complex

**Exit criteria**: Conversational interaction with the bot about KB contents.

## Cost

| Service | Cost |
|---------|------|
| Telegram Bot API | Free |
| Claude Haiku (~100 summaries/week) | ~$1-3/mo |
| Nexa local LLM (NPU) | Free |
| RSS/Atom feeds | Free |
| SMTP (Gmail) | Free |
| **Total** | **~$1-3/mo** |
