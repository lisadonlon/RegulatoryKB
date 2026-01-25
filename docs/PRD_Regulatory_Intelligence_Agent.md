# Product Requirements Document: Regulatory Intelligence Agent

**Product**: RegulatoryKB - Regulatory Intelligence Module
**Author**: Lisa Donlon, DLSC / Vertigenius
**Version**: 1.0 Draft
**Date**: January 2026

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
| FR-6.5 | Streamlit page for intelligence dashboard | Should |
| FR-6.6 | Interactive approval for downloads (optional) | Could |
| FR-6.7 | Scheduled execution (Windows Task Scheduler / cron) | Should |

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
│   ├── fetcher.py       # Newsletter fetching & parsing
│   ├── filter.py        # Content filtering & relevance scoring
│   ├── analyzer.py      # KB comparison & gap detection
│   ├── summarizer.py    # LLM-powered summary generation
│   ├── emailer.py       # Email composition & delivery
│   └── scheduler.py     # Scheduled execution support
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
│    Index-of-Indexes → Parse HTML → Extract entries               │
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
│ 4. DOWNLOAD                                                      │
│    Download PDFs → Validate → Import to KB → Tag source          │
│    Output: List[DownloadResult]                                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. SUMMARIZE                                                     │
│    LLM prompt → Generate layperson summary → Format output       │
│    Output: List[Summary]                                         │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. EMAIL                                                         │
│    Compose HTML → Group by category → Send via SMTP              │
│    Output: EmailResult                                           │
└─────────────────────────────────────────────────────────────────┘
```

### 5.4 Dependencies

**New Dependencies**:
```
# requirements.txt additions
beautifulsoup4>=4.12.0    # HTML parsing
lxml>=5.0.0               # Fast HTML parser
anthropic>=0.18.0         # Claude API for summaries
openai>=1.0.0             # OpenAI API (alternative)
jinja2>=3.1.0             # Email templating
python-dotenv>=1.0.0      # Secure credential loading
schedule>=1.2.0           # Task scheduling
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

### Phase 1: Core Fetching & Filtering (MVP)
**Duration**: 1-2 weeks

- [ ] Newsletter fetcher module
- [ ] HTML parsing for Index-of-Indexes
- [ ] Basic category filtering
- [ ] Keyword-based filtering
- [ ] CLI command: `regkb intel fetch`

### Phase 2: KB Integration
**Duration**: 1 week

- [ ] URL-based duplicate detection
- [ ] Title similarity matching
- [ ] Auto-download for free documents
- [ ] Auto-import to KB with tagging
- [ ] CLI command: `regkb intel sync`

### Phase 3: LLM Summarization
**Duration**: 1 week

- [ ] Anthropic/OpenAI integration
- [ ] Summary prompt engineering
- [ ] Layperson language generation
- [ ] Configurable summary styles
- [ ] CLI command: `regkb intel summary`

### Phase 4: Email Delivery
**Duration**: 1 week

- [ ] HTML email templates (Jinja2)
- [ ] SMTP integration
- [ ] Weekly digest generation
- [ ] Monthly compilation
- [ ] CLI command: `regkb intel email`

### Phase 5: Automation & Polish
**Duration**: 1 week

- [ ] Scheduled execution support
- [ ] Streamlit dashboard page
- [ ] Error handling & retry logic
- [ ] Documentation & examples

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
| **Approval Workflow** | Require approval before downloads | User control over what enters KB |
| **Historical Backfill** | Start fresh | Focus on current/future updates |
| **Team Recipients** | Static list (configurable in YAML) | Simple initial implementation |

---

## 11. Appendix

### A. Index-of-Indexes Entry Structure

**Technical Note**: The site loads data dynamically from CSV files via JavaScript (PapaParse). We should either:
1. Fetch the underlying CSV sources directly (preferred - faster, more reliable)
2. Use a headless browser to render the JavaScript (fallback)

**Data Fields** (from HTML table):
| Column | Description | Notes |
|--------|-------------|-------|
| Copilot | AI search link | Bing Copilot query |
| Date | Entry date | May link to date-specific page |
| Agency | Regulatory body | FDA, EU, ISO, etc. |
| Category | Classification | Standards, Guidance, etc. |
| Title | Description | Links to source document |

**Filters Available**:
- Date (multi-select dropdown)
- Agency (single-select)
- Category (single-select)
- Title (text search)

**CSV Source**: Data loaded from `csv_sources.txt` - should investigate for direct access

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

**Document Status**: Draft for Review
**Next Steps**: Review with stakeholder, prioritize features, begin Phase 1 implementation
