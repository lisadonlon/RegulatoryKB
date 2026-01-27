# Product Requirements Document: Regulatory Intelligence Agent

**Product**: RegulatoryKB - Regulatory Intelligence Module
**Author**: Lisa Donlon, DLSC / Vertigenius
**Version**: 2.0 (Implementation Complete)
**Date**: January 2026 (updated January 27, 2026)

---

## 1. Executive Summary

Extend RegulatoryKB with an automated regulatory intelligence agent that monitors weekly regulatory updates, filters content based on user interests, identifies new documents for the knowledge base, and generates team-friendly summaries delivered via email.

### Problem Statement

Regulatory professionals spend significant time manually reviewing weekly newsletters, identifying relevant updates, downloading documents, and communicating changes to their teams. This process is:
- Time-consuming (hours per week)
- Error-prone (easy to miss relevant updates)
- Inconsistent (summary quality varies)
- Disconnected from existing document management

### Solution

An intelligent agent that automates the regulatory intelligence workflow:
1. **Fetch** weekly updates from Index-of-Indexes
2. **Filter** based on configured interests
3. **Analyze** against existing knowledge base
4. **Download** new relevant documents
5. **Summarize** in layperson terms
6. **Deliver** via informative email

---

## 2. User Stories

### Primary User: Regulatory Consultant (Lisa)

**US-1**: As a regulatory consultant, I want to receive a filtered summary of weekly regulatory updates relevant to medical devices, so I don't waste time reading pharma-focused content.

**US-2**: As a regulatory consultant, I want the system to automatically check if new guidance documents are already in my knowledge base, so I don't download duplicates.

**US-3**: As a regulatory consultant, I want new documents automatically downloaded and added to my KB with proper metadata, so my archive stays current.

**US-4**: As a regulatory consultant, I want layperson summaries of technical regulatory updates, so I can share them with my non-regulatory team members.

**US-5**: As a regulatory consultant, I want a monthly digest email I can forward to my team at Vertigenius, so everyone stays informed without me manually writing updates.

### Secondary User: Team Members (Vertigenius)

**US-6**: As a team member, I want to receive clear, jargon-free summaries of regulatory changes, so I understand how they affect our work.

---

## 3. Functional Requirements

### 3.1 Newsletter Fetching

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1.1 | Fetch content from Index-of-Indexes URL | Must |
| FR-1.2 | Parse newsletter entries (date, agency, category, title, link) | Must |
| FR-1.3 | Support date range filtering (this week, custom range) | Must |
| FR-1.4 | Handle pagination if newsletter spans multiple pages | Should |
| FR-1.5 | Cache fetched content to avoid repeated requests | Should |
| FR-1.6 | Graceful handling of site unavailability | Must |

**Source URL**: `https://martincking.github.io/Index-of-Indexes/?date=&agency=&category=&title=`

### 3.2 Content Filtering

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-2.1 | Filter by category: Standards updates | Must |
| FR-2.2 | Filter by category: Medical device regulatory updates | Must |
| FR-2.3 | Filter by category: AI regulation updates | Must |
| FR-2.4 | Filter by category: Digital health guidance | Must |
| FR-2.5 | Exclude: Pharma updates (unless combination device) | Must |
| FR-2.6 | Exclude: ICH updates (unless combination device) | Must |
| FR-2.7 | Configurable filter rules via YAML | Should |
| FR-2.8 | Keyword-based relevance scoring | Should |
| FR-2.9 | LLM-assisted relevance classification | Could |

**Filter Configuration Example**:
```yaml
intelligence:
  interests:
    include:
      - medical devices
      - standards
      - AI regulation
      - digital health
      - SaMD
      - MDR
      - IVDR
      - FDA guidance
    exclude:
      - pharma
      - ICH
      - drug
      - biologics
    conditional:
      - term: "combination device"
        override_exclude: [pharma, ICH]
```

### 3.3 Knowledge Base Integration

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-3.1 | Check if linked document already exists in KB (by URL) | Must |
| FR-3.2 | Check if linked document already exists in KB (by title similarity) | Must |
| FR-3.3 | Identify freely downloadable documents (PDF links) | Must |
| FR-3.4 | Flag documents requiring manual download (paywalled) | Should |
| FR-3.5 | Queue new documents for approval before download | Must |
| FR-3.6 | CLI/email interface to approve/reject pending downloads | Must |
| FR-3.7 | Download approved documents to specified location | Must |
| FR-3.8 | Import approved documents to KB with metadata | Must |
| FR-3.9 | Tag imported documents with source (Index-of-Indexes) | Should |
| FR-3.10 | Auto-detect prior versions on import (identifier matching) | Must |
| FR-3.11 | Auto-supersede prior version with similarity gate (configurable threshold, default 15%) | Must |
| FR-3.12 | Content validation — verify extracted text matches claimed title (advisory) | Should |
| FR-3.13 | PDF validation — magic byte checking, detect HTML error pages, ZIPs, images | Must |

### 3.4 Summary Generation

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-4.1 | Generate layperson summary for each relevant update | Must |
| FR-4.2 | Explain regulatory impact in plain language | Must |
| FR-4.3 | Highlight action items (if any) | Should |
| FR-4.4 | Group summaries by category | Must |
| FR-4.5 | Include links to source documents | Must |
| FR-4.6 | Support configurable summary length (brief/detailed) | Should |
| FR-4.7 | Use LLM for summary generation | Must |

**Summary Format**:
```
## Medical Device Updates

### [Title of Update]
**Source**: FDA | **Date**: Jan 20, 2026 | **Status**: New in KB

**What happened**: [1-2 sentence plain language explanation]

**Why it matters**: [Impact on medical device companies]

**Action needed**: [Any required response, or "Information only"]

[Read full document →](link)
```

### 3.5 Email Delivery

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-5.1 | Generate HTML email with formatted summaries | Must |
| FR-5.2 | Weekly digest email (configurable day/time) | Must |
| FR-5.3 | Monthly compilation email for team distribution | Must |
| FR-5.4 | Daily alert email for high-relevance items (threshold-based) | Must |
| FR-5.5 | Include "New to KB" section with download confirmations | Should |
| FR-5.6 | Include "Pending Approval" section with approve/reject links | Must |
| FR-5.7 | Send via SMTP (configurable server) | Must |
| FR-5.8 | Support multiple recipients | Should |
| FR-5.9 | Plain text fallback for email clients | Should |

**Email Structure**:
```
Subject: Regulatory Intelligence Weekly - Jan 20-26, 2026

SUMMARY
- 3 Medical Device updates
- 2 Standards updates
- 1 AI Regulation update
- 4 documents added to KB

MEDICAL DEVICE UPDATES
[summaries...]

STANDARDS UPDATES
[summaries...]

AI REGULATION
[summaries...]

NEW IN YOUR KNOWLEDGE BASE
- [Document 1] - Downloaded and indexed
- [Document 2] - Downloaded and indexed

REQUIRES ATTENTION
- [Document 3] - Manual download required (paywalled)

---
Generated by RegulatoryKB Intelligence Agent
Vertigenius Regulatory Consulting
```

### 3.6 User Interface

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-6.1 | CLI command: `regkb intel fetch` - Fetch this week's updates | Must |
| FR-6.2 | CLI command: `regkb intel summary` - Generate summary | Must |
| FR-6.3 | CLI command: `regkb intel email` - Send email digest | Must |
| FR-6.4 | CLI command: `regkb intel run` - Full workflow | Must |
| FR-6.5 | CLI command: `regkb intel pending` - List pending approvals | Must |
| FR-6.6 | CLI command: `regkb intel approve/reject` - Approve/reject downloads | Must |
| FR-6.7 | CLI command: `regkb intel poll` - Poll IMAP for reply-based downloads | Must |
| FR-6.8 | Streamlit page for intelligence dashboard | Should |
| FR-6.9 | Scheduled execution (Windows Task Scheduler / cron) | Should |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1.1 | Newsletter fetch time | < 30 seconds |
| NFR-1.2 | Document download time | < 60 seconds per document |
| NFR-1.3 | Summary generation time | < 10 seconds per item |
| NFR-1.4 | Email generation time | < 30 seconds |

### 4.2 Reliability

| ID | Requirement |
|----|-------------|
| NFR-2.1 | Retry failed downloads up to 3 times |
| NFR-2.2 | Log all operations for troubleshooting |
| NFR-2.3 | Continue processing if individual items fail |
| NFR-2.4 | Store intermediate results to resume after failure |

### 4.3 Security

| ID | Requirement |
|----|-------------|
| NFR-3.1 | Store SMTP credentials securely (not in config file) |
| NFR-3.2 | No sensitive data in logs |
| NFR-3.3 | Validate downloaded files before import |

### 4.4 Configurability

| ID | Requirement |
|----|-------------|
| NFR-4.1 | All filter rules configurable via YAML |
| NFR-4.2 | Email settings configurable via YAML |
| NFR-4.3 | LLM provider configurable (OpenAI, Anthropic, local) |
| NFR-4.4 | Download location configurable |

---

## 5. Technical Architecture

### 5.1 New Modules

```
scripts/regkb/
├── intelligence/
│   ├── __init__.py
│   ├── fetcher.py          # Newsletter fetching & CSV parsing
│   ├── filter.py           # Content filtering & relevance scoring
│   ├── analyzer.py         # KB comparison & gap detection
│   ├── summarizer.py       # Claude LLM summary generation + caching
│   ├── emailer.py          # Email composition & SMTP delivery
│   ├── digest_tracker.py   # Entry ID tracking across digests (SQLite)
│   ├── url_resolver.py     # URL resolution (LinkedIn, social media, paid domains)
│   ├── reply_handler.py    # IMAP polling & reply-based download processing
│   └── scheduler.py        # Windows Task Scheduler XML & batch script generation
```

### 5.2 Configuration Extensions

```yaml
# config/config.yaml additions

intelligence:
  source_url: "https://martincking.github.io/Index-of-Indexes/"

  schedule:
    weekly_day: "monday"      # Day to run weekly digest
    weekly_time: "08:00"      # Time to run
    monthly_day: 1            # Day of month for team digest
    daily_alerts: true        # Send daily email for high-relevance items
    daily_alert_time: "09:00" # Time for daily alerts
    daily_alert_threshold: 0.9  # Relevance score threshold for daily alerts

  filters:
    include_categories:
      - "Medical Devices"
      - "Standards"
      - "Digital Health"
      - "AI/ML"
    exclude_categories:
      - "Pharmaceuticals"
      - "Biologics"
    include_keywords:
      - "MDR"
      - "IVDR"
      - "FDA"
      - "guidance"
      - "SaMD"
    exclude_keywords:
      - "drug"
      - "clinical trial"
    combination_device_override: true

  downloads:
    auto_download: false       # Require approval before downloading
    require_approval: true     # Show pending downloads for user approval
    target_directory: "downloads/intelligence"

  summarization:
    provider: "anthropic"     # Claude - best for medical/regulatory accuracy
    model: "claude-3-5-haiku" # Fast, cost-effective for summaries
    style: "layperson"        # Plain language for team distribution
    max_length: 200           # words per summary
    # Note: Uses Claude Pro Max API key from environment

  email:
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    sender: "regulatory@vertigenius.com"
    recipients:
      - "team@vertigenius.com"
    weekly_subject: "Regulatory Intelligence Weekly - {date_range}"
    monthly_subject: "Regulatory Intelligence Monthly - {month} {year}"
```

### 5.3 Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    REGULATORY INTELLIGENCE AGENT                 │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. FETCH                                                         │
│    Index-of-Indexes CSV → Parse entries → Freshness filter       │
│    Output: List[NewsletterEntry]                                 │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. FILTER                                                        │
│    Apply category filters → Keyword matching → Relevance score   │
│    Output: List[RelevantEntry] (filtered & scored)               │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. ANALYZE                                                       │
│    Check KB by URL → Check by title → Identify gaps              │
│    Output: {in_kb: [], new: [], manual_download: []}             │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. SUMMARIZE                                                     │
│    Claude API → Layperson summary → Cache in SQLite              │
│    Output: List[Summary] (cached for reuse)                      │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. EMAIL (with entry IDs)                                        │
│    Compose HTML → Group by category → Assign entry IDs           │
│    → Track in digest DB → Send via SMTP                          │
│    Output: EmailResult + DigestEntries                            │
└─────────────────────────────────────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
┌────────────────────────┐  ┌────────────────────────────────────┐
│ 6a. REPLY-TO-DOWNLOAD  │  │ 6b. CLI DOWNLOAD                   │
│   IMAP poll for replies │  │   regkb intel download-entry IDS   │
│   Parse entry IDs       │  │   Manual download trigger          │
│   Resolve URLs          │  └────────────────────────────────────┘
│   (LinkedIn, social)    │               │
└────────────────────────┘               │
                    │                     │
                    └──────────┬──────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. DOWNLOAD & IMPORT                                             │
│    Resolve URL → Download PDF → Validate (magic bytes)           │
│    → Import to KB → Extract text (PyMuPDF / OCR)                 │
│    → Detect prior version → Similarity gate → Auto-supersede     │
│    → Content validation (title vs text)                          │
│    Output: ProcessedDownload (with version_diff, content_warning)│
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. CONFIRMATION EMAIL                                            │
│    Send results: successes, failures, manual URL needed          │
│    Include version diff details and content warnings             │
│    Output: EmailResult                                           │
└─────────────────────────────────────────────────────────────────┘
```

### 5.4 Dependencies

**Dependencies** (declared in `pyproject.toml`):
```
# Core
PyMuPDF (fitz)            # PDF text extraction
chromadb                  # Vector embeddings database
sentence-transformers     # Embedding model (all-MiniLM-L6-v2)
requests                  # HTTP downloads
tqdm                      # Progress bars
pyyaml                    # Configuration
python-dotenv             # Environment variable loading

# Intelligence module
beautifulsoup4            # HTML parsing (fallback)
lxml                      # Fast HTML/CSV parser
anthropic                 # Claude API for LLM summaries

# Optional: OCR
pytesseract               # Tesseract OCR binding
Pillow                    # Image processing for OCR
```

---

## 6. User Interface Mockups

### 6.1 CLI Output

```
$ regkb intel run

Regulatory Intelligence Agent
=============================

[1/6] Fetching Index-of-Indexes...
      Found 47 entries for Jan 20-26, 2026

[2/6] Filtering by interests...
      Medical Devices: 12 entries
      Standards: 5 entries
      AI/Digital Health: 3 entries
      Excluded: 27 entries (pharma, ICH, etc.)

[3/6] Checking against knowledge base...
      Already in KB: 8 documents
      New documents: 7 documents
      Manual download required: 5 documents

[4/6] Downloading new documents...
      ✓ FDA Guidance on AI-Enabled Devices (2.3 MB)
      ✓ MDCG 2026-1 Clinical Evidence (1.1 MB)
      ✓ ISO 13485:2026 Amendment (0.8 MB)
      ... 4 more downloaded

[5/6] Generating summaries...
      ✓ 20 summaries generated

[6/6] Composing email...
      ✓ Weekly digest ready

Send email now? [Y/n]: y
      ✓ Email sent to team@vertigenius.com

Summary saved to: reports/intel_2026-01-26.html
```

### 6.2 Email Preview

```
┌────────────────────────────────────────────────────────────────┐
│ From: regulatory@vertigenius.com                               │
│ To: team@vertigenius.com                                       │
│ Subject: Regulatory Intelligence Weekly - Jan 20-26, 2026      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  REGULATORY INTELLIGENCE WEEKLY                                │
│  January 20-26, 2026                                           │
│                                                                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                │
│  THIS WEEK AT A GLANCE                                         │
│  • 12 Medical Device updates                                   │
│  • 5 Standards updates                                         │
│  • 3 AI/Digital Health updates                                 │
│  • 7 new documents added to your KB                            │
│                                                                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                │
│  MEDICAL DEVICE UPDATES                                        │
│                                                                │
│  📄 FDA Guidance: AI-Enabled Medical Devices                   │
│     Source: FDA | Jan 23, 2026 | ✅ Added to KB                │
│                                                                │
│     The FDA released final guidance on AI-enabled medical      │
│     devices, clarifying requirements for algorithm changes     │
│     and predetermined change control plans.                    │
│                                                                │
│     Why it matters: Companies with AI/ML devices need to       │
│     review their change management processes against this      │
│     new framework.                                             │
│                                                                │
│     [Read full guidance →]                                     │
│                                                                │
│  ─────────────────────────────────────────────────────────────│
│                                                                │
│  📄 MDCG 2026-1: Clinical Evidence Requirements                │
│     Source: EU | Jan 21, 2026 | ✅ Added to KB                 │
│     ...                                                        │
│                                                                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                │
│  NEW IN YOUR KNOWLEDGE BASE                                    │
│  These documents were automatically downloaded and indexed:    │
│                                                                │
│  ✓ FDA Guidance on AI-Enabled Devices                          │
│  ✓ MDCG 2026-1 Clinical Evidence                               │
│  ✓ ISO 13485:2026 Amendment                                    │
│  ✓ ... 4 more                                                  │
│                                                                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                │
│  REQUIRES YOUR ATTENTION                                       │
│  These documents need manual download:                         │
│                                                                │
│  ⚠️ ISO 14971:2026 (Paid standard)                             │
│     [Visit ISO store →]                                        │
│                                                                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                │
│  Generated by RegulatoryKB Intelligence Agent                  │
│  Vertigenius Regulatory Consulting                             │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 7. Implementation Phases

### Phase 1: Core Fetching & Filtering (MVP) -- COMPLETE
**Duration**: 1-2 weeks

- [x] Newsletter fetcher module
- [x] HTML parsing for Index-of-Indexes (CSV direct fetch via PapaParse source)
- [x] Basic category filtering
- [x] Keyword-based filtering with relevance scoring
- [x] CLI command: `regkb intel fetch`
- [x] News freshness filter (configurable max age, default 14 days)

### Phase 2: KB Integration -- COMPLETE
**Duration**: 1 week

- [x] URL-based duplicate detection
- [x] Title similarity matching
- [x] Auto-download for free documents
- [x] Auto-import to KB with tagging
- [x] CLI command: `regkb intel sync`
- [x] Pending approval workflow (`intel pending`, `intel approve`, `intel reject`)

### Phase 3: LLM Summarization -- COMPLETE
**Duration**: 1 week

- [x] Anthropic integration (Claude API)
- [x] Summary prompt engineering
- [x] Layperson language generation (what happened / why it matters / action needed)
- [x] Configurable summary styles
- [x] CLI command: `regkb intel summary`
- [x] Summary caching with SQLite (`intel cache --stats`, `--clear`)

### Phase 4: Email Delivery -- COMPLETE
**Duration**: 1 week

- [x] HTML email templates (inline CSS, responsive)
- [x] SMTP integration (Gmail app passwords)
- [x] Weekly digest generation with entry IDs
- [x] Monthly compilation
- [x] Daily alert emails (critical/high keyword triggers)
- [x] CLI command: `regkb intel email` (`--type weekly|daily|test`)

### Phase 5: Automation & Polish -- MOSTLY COMPLETE
**Duration**: 1 week

- [x] Scheduled execution support (Windows Task Scheduler XML + batch script generation)
- [ ] Streamlit dashboard page
- [x] Error handling & retry logic
- [x] Documentation (comprehensive README with Mermaid architecture diagram)

### Phase 6: Email Reply-Based Downloads -- COMPLETE
**Duration**: 1 week

- [x] Entry ID system (YYYY-MMDD-NN format) in digest emails
- [x] Digest tracker database for entry lookup
- [x] URL resolver for LinkedIn/social media links (with paid domain detection)
- [x] IMAP polling for digest reply processing (trusted sender validation)
- [x] Confirmation emails with download results (version diff + content warnings included)
- [x] CLI commands: `poll`, `resolve-url`, `download-entry`, `digest-entries`
- [x] Auto version detection on reply-triggered imports
- [x] Content validation on reply-triggered imports

**Workflow**: Reply to digest with "Download: 07, 12" → IMAP poll detects reply → resolve URLs → download → validate PDF → import to KB → detect prior versions → send confirmation email

### Phase 7: EVS Standards Integration (Future)
**Duration**: TBD

- [ ] Detect standards updates available via EVS subscription
- [ ] EVS API authentication with user credentials
- [ ] Automated download of subscribed standards
- [ ] Auto-import to KB with standards metadata
- [ ] Handle standard revisions/amendments

**Notes**:
- For personal business use only (no redistribution licensing concerns)
- User purchases standards via their own EVS account
- Extends URL resolver to handle EVS-available domains (ISO, IEC, etc.)

---

## 8. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time saved per week | 2+ hours | User feedback |
| Relevant updates captured | > 95% | Manual verification |
| False positives (irrelevant) | < 10% | Manual verification |
| Auto-download success rate | > 90% | System logs |
| Email delivery success | 100% | SMTP logs |
| Summary quality rating | 4+/5 | User feedback |

---

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Index-of-Indexes format changes | High | Medium | Abstract parser, monitor for changes |
| LLM API costs | Medium | High | Use efficient models (Haiku), cache results |
| SMTP blocking | Medium | Low | Use authenticated SMTP, monitor deliverability |
| Download rate limiting | Medium | Medium | Respect delays, implement backoff |
| Incorrect filtering | High | Medium | Configurable rules, manual override option |

---

## 10. Decisions (Resolved)

| Question | Decision | Rationale |
|----------|----------|-----------|
| **LLM Provider** | Claude (Anthropic) | Better accuracy for medical/regulatory terminology, lower hallucination risk, user has Pro Max access |
| **Email Frequency** | Weekly digest + daily alerts for high-relevance items only | Balance information flow without inbox overload |
| **Approval Workflow** | Both CLI and email links | CLI for power users, email for convenience |
| **Daily Alert Trigger** | Keyword match | Specific terms (MDR, IVDR, FDA guidance, etc.) trigger immediate alerts |
| **Monthly Format** | Curated highlights | Top 10-15 items with expanded summaries, not full compilation |
| **Historical Backfill** | Start fresh | Focus on current/future updates |
| **Team Recipients** | Static list (configurable in YAML) | Simple initial implementation |
| **Approval via Web Endpoint** | Replaced by IMAP reply processing | Reply-to-download is simpler — no server process needed, works from any email client |
| **Supersession Safety** | Similarity gate (15% minimum) + content validation | Prevents wrong PDFs from superseding correct documents in the KB |
| **CSV vs HTML Parsing** | Direct CSV fetch | Bypasses JavaScript rendering, faster and more reliable |
| **Summary Caching** | SQLite-backed cache | Avoids redundant LLM API calls for already-summarized entries |

### Approval & Download Workflow Detail

The system supports three download interfaces:

**CLI Approval (pending queue):**
```bash
$ regkb intel pending          # List pending downloads
$ regkb intel approve 1 2 3    # Approve items by ID
$ regkb intel reject 4         # Reject item
$ regkb intel approve --all    # Approve all pending
$ regkb intel download         # Download and import approved items
```

**Email Reply-to-Download (Phase 6):**
- Digest emails include entry IDs (e.g., `[07]`, `[12]`) next to each item
- Reply to the digest with "Download: 07, 12" (or just "07, 12")
- Run `regkb intel poll` to check IMAP for replies
- System resolves URLs, downloads PDFs, imports to KB, sends confirmation email
- Trusted sender validation against configured recipient list

**CLI Direct Download:**
```bash
$ regkb intel download-entry 07 12   # Download specific digest entries by ID
$ regkb intel resolve-url URL        # Test URL resolution for a specific link
```

### Daily Alert Keywords

Default high-priority keywords (configurable):
```yaml
daily_alert_keywords:
  critical:  # Always alert
    - "MDR"
    - "IVDR"
    - "FDA final guidance"
    - "ISO 13485"
    - "recall"
    - "safety alert"
  high:  # Alert if 2+ matches
    - "SaMD"
    - "AI/ML"
    - "digital health"
    - "cybersecurity"
    - "MDCG"
```

### Monthly Digest Format

**Curated Highlights Structure:**
1. Executive Summary (3-5 sentences)
2. Top 10-15 Most Important Updates (expanded summaries)
3. Key Action Items (bulleted list)
4. Documents Added to KB This Month
5. Links to Weekly Digests for Full Details

---

## 11. Appendix

### A. Index-of-Indexes Entry Structure

**Implementation**: The fetcher directly downloads the CSV source files referenced by the site's `csv_sources.txt`. This bypasses JavaScript rendering entirely and is faster and more reliable than HTML parsing.

**Data Fields** (from CSV):
| Column | Description | Notes |
|--------|-------------|-------|
| Date | Entry date | Parsed for freshness filtering |
| Agency | Regulatory body | FDA, EU, ISO, TGA, Health Canada, etc. |
| Category | Classification | Standards, Guidance, Regulation, etc. |
| Title | Description | Used for KB matching and LLM summarization |
| Link | Source URL | Resolved via url_resolver for social/redirect links |

**Freshness Filter**: Entries older than `max_news_age_days` (default 14) are excluded to avoid processing stale content on first run or after gaps.

### B. Example Filter Rules

```yaml
# Combination device detection
combination_device_keywords:
  - "drug-device"
  - "combination product"
  - "drug eluting"
  - "prefilled"
  - "delivery device"

# When these appear with pharma/ICH content, include it
```

### C. Summary Prompt Template

```
You are a regulatory affairs expert writing for a non-technical audience.

Summarize this regulatory update in 2-3 sentences:
- What changed or was announced
- Why it matters for medical device companies
- Any action needed

Document: {title}
Source: {agency}
Content: {content_snippet}

Write in plain English, avoid jargon. If technical terms are necessary, briefly explain them.
```

---

**Document Status**: Phases 1-6 Implemented, Phase 7 (EVS) Future
**Implementation Notes**: All core functionality is operational. The email-based approval workflow (FR-6.7 web endpoint) was replaced by IMAP reply processing (Phase 6), which proved more practical. The Streamlit dashboard (Phase 5) remains as a future enhancement. Features beyond original scope — OCR fallback extraction, document diff/comparison, automatic version detection with similarity gate, and content validation — were added during implementation and are documented in FR-3.10 through FR-3.13.
