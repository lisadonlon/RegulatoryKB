**Product Requirements Document**

**Regulatory Knowledge Base System**

| Version: | 1.0 |
| :---- | :---- |
| **Date:** | January 2026 |
| **Author:** | Lisa Donlon, DLSC |

# **1\. Executive Summary**

A local knowledge base system for managing regulatory documents (guidance, standards, legislation) with natural language search capability. Addresses the core problem of repeatedly downloading duplicate documents due to poor organisation and discoverability.

**Primary objective:** Stop re-downloading documents by knowing what exists in the collection and being able to find it quickly.

**Security requirement:** Complete separation from client-confidential work through directory isolation.

# **2\. User Stories**

**As a regulatory consultant, I want to:**

* Import scattered PDFs from multiple locations into a centralised, organised archive  
* Automatically detect and skip duplicate documents  
* Search my collection using natural language queries  
* Track document metadata (source, version, jurisdiction, type)  
* Maintain version history whilst defaulting to the most recent version  
* Verify document provenance (where it came from, when acquired)  
* Add new documents with minimal friction  
* Run everything locally without API dependencies or privacy concerns

# **3\. Functional Requirements**

## **3.1 Document Import**

* **FR-1.1:** Scan specified directories recursively for PDF files  
* **FR-1.2:** Calculate SHA-256 hash for duplicate detection  
* **FR-1.3:** Skip files already in the knowledge base (based on hash)  
* **FR-1.4:** Copy unique PDFs to standardised archive location  
* **FR-1.5:** Prompt user for metadata during import (with intelligent defaults)  
* **FR-1.6:** Support batch import operations  
* **FR-1.7:** Generate import report (files added, duplicates skipped, errors)

## **3.2 Metadata Management**

* **FR-2.1:** Capture mandatory metadata: title, document type, jurisdiction  
* **FR-2.2:** Capture optional metadata: source URL, version, description  
* **FR-2.3:** Auto-populate download date and file hash  
* **FR-2.4:** Support manual metadata correction/updates  
* **FR-2.5:** Flag most recent version of multi-version documents  
* **FR-2.6:** Track document relationships (superseded by, replaces, etc.)

## **3.3 Text Extraction**

* **FR-3.1:** Extract text from PDFs to Markdown format  
* **FR-3.2:** Preserve basic structure (headings, lists where detectable)  
* **FR-3.3:** Store extracted text separately from original PDFs  
* **FR-3.4:** Handle extraction failures gracefully (log and continue)  
* **FR-3.5:** Support re-extraction if initial attempt fails or produces poor results

## **3.4 Search Capability**

* **FR-4.1:** Accept natural language queries  
* **FR-4.2:** Return ranked list of relevant documents  
* **FR-4.3:** Display: title, type, jurisdiction, relevance score, file path  
* **FR-4.4:** Support filtering by: document type, jurisdiction, date range  
* **FR-4.5:** Show excerpt/context where match was found  
* **FR-4.6:** Limit results to latest versions by default (with option to include all)

## **3.5 Document Addition**

* **FR-5.1:** Add single document via command line  
* **FR-5.2:** Download document from URL directly into system  
* **FR-5.3:** Prompt for metadata during addition  
* **FR-5.4:** Automatically check for duplicates before adding

## **3.6 Database Operations**

* **FR-6.1:** List all documents with filtering options  
* **FR-6.2:** Show document details by ID or hash  
* **FR-6.3:** Update metadata for existing documents  
* **FR-6.4:** Mark documents as superseded/outdated  
* **FR-6.5:** Generate statistics (total docs, by type, by jurisdiction, etc.)

# **4\. Non-Functional Requirements**

## **4.1 Security**

* **NFR-1.1:** Entire system contained within \~/RegulatoryKB/ directory  
* **NFR-1.2:** No access to directories outside project scope  
* **NFR-1.3:** All processing runs locally (no external API calls for core functionality)  
* **NFR-1.4:** No sensitive data storage (public documents only)

## **4.2 Performance**

* **NFR-2.1:** Search results returned within 2 seconds for typical queries  
* **NFR-2.2:** Import rate: minimum 10 documents per minute  
* **NFR-2.3:** Support database of 1000+ documents without degradation

## **4.3 Usability**

* **NFR-3.1:** Command-line interface with clear, concise output  
* **NFR-3.2:** Sensible defaults to minimise required user input  
* **NFR-3.3:** Helpful error messages with recovery suggestions  
* **NFR-3.4:** Progress indicators for long-running operations

## **4.4 Reliability**

* **NFR-4.1:** Atomic operations (don't corrupt database on failure)  
* **NFR-4.2:** Graceful handling of malformed PDFs  
* **NFR-4.3:** Database backups before destructive operations  
* **NFR-4.4:** Operation logging for troubleshooting

## **4.5 Maintainability**

* **NFR-5.1:** Clear code structure with docstrings  
* **NFR-5.2:** Configuration via files (not hardcoded)  
* **NFR-5.3:** Modular design for future enhancements  
* **NFR-5.4:** Database migrations supported

# **5\. Technical Architecture**

## **5.1 Technology Stack**

* **Language:** Python 3.9+  
* **Database:** SQLite 3.35+ (with FTS5 for full-text search)  
* **PDF Processing:** pymupdf (PyMuPDF)  
* **Embeddings:** sentence-transformers (all-MiniLM-L6-v2 model)  
* **Vector Search:** ChromaDB or SQLite with vector extension  
* **CLI Framework:** argparse or click

## **5.2 Directory Structure**

\~/RegulatoryKB/  
├── archive/                      \# Permanent PDF storage  
├── extracted/                    \# Markdown extractions  
├── db/  
│   ├── regulatory.db            \# Main SQLite database  
│   └── backups/                 \# Automated backups  
├── scripts/                      \# Python application code  
├── config/                       \# Configuration files  
├── logs/                         \# Application logs  
├── .venv/                        \# Python virtual environment  
├── requirements.txt  
├── README.md  
└── setup.py

## **5.3 Database Schema**

The system uses SQLite with the following core tables:

### **Documents Table**

| Column | Type | Description |
| :---- | :---- | :---- |
| id | INTEGER | Primary key |
| hash | TEXT | SHA-256 of PDF file |
| title | TEXT | Human-readable title |
| document\_type | TEXT | Type: guidance, standard, regulation, etc. |
| jurisdiction | TEXT | Jurisdiction: EU, FDA, ISO, etc. |
| version | TEXT | Document version identifier |
| is\_latest | BOOLEAN | Flag for most recent version |
| source\_url | TEXT | Origin URL if available |
| file\_path | TEXT | Path to PDF in archive |

Additional tables: embeddings (for vector search), import\_batches (audit trail), documents\_fts (full-text search index).

# **6\. User Interface**

The system provides a command-line interface with the following core commands:

### **Import Documents**

regkb import /path/to/pdfs \--recursive

### **Search**

regkb search "MDR Article 120 timeline"  
regkb search "combination product classification" \--type guidance \--jurisdiction FDA

### **Add Single Document**

regkb add document.pdf  
regkb add https://example.com/guidance.pdf

### **List Documents**

regkb list \--type standard \--jurisdiction ISO

### **Statistics**

regkb stats

# **7\. Success Metrics**

* **Primary:** User stops re-downloading documents they already have  
* **Search effectiveness:** Relevant document found in top 3 results \>80% of queries  
* **Import efficiency:** 1000 documents imported and indexed in \<2 hours  
* **System adoption:** Becomes primary source for regulatory document retrieval within 1 month

# **8\. Testing Requirements**

## **8.1 Unit Tests**

* Hash calculation consistency  
* Duplicate detection logic  
* Metadata validation  
* Database CRUD operations  
* Search ranking algorithm

## **8.2 Integration Tests**

* End-to-end import workflow  
* Search with various query types  
* Version control (supersession) logic  
* Backup and restore operations

## **8.3 User Acceptance Tests**

* Import 100 diverse regulatory PDFs  
* Perform 20 realistic search queries  
* Verify results accuracy  
* Test error recovery scenarios

# **9\. Future Enhancements (Out of Scope for v1.0)**

* Web interface for search  
* OCR for scanned documents  
* Automated document download from known sources  
* Citation extraction and linking  
* Document comparison/diff functionality  
* Export to citation managers  
* Multi-user support  
* Cloud backup integration  
* Mobile app  
* Integration with reference managers (Zotero, Mendeley)