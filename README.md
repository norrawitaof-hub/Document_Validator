# AI-Assisted Order-to-Cash Demo

This repository documents a demo implementation of a standardized, AI-assisted order-to-cash workflow for a trading company. The goal is to reduce manual effort, improve accuracy, and enable scale without linear headcount growth.

## Problem Statement (As-Is)
- **Order intake is unstructured and scattered**, leading to fragmented communication.
- **Re-keying data multiple times** causes delays and error risk.
- **Ambiguous product naming** creates SKU mismatches.
- **Time lost on follow-ups** slows delivery and invoicing.
- Overall: **manual processes** drive high error rates and dependency on individuals.

## Target State (To-Be)
- **Central order system** consolidates all intake channels.
- **AI-assisted extraction** captures intent, quantities, and client data from unstructured messages.
- **Integrated delivery and invoicing** keeps ERP data aligned and reduces manual entry.
- **Human-in-the-loop (HITL) controls** safeguard low-confidence cases.
- **Analytics** provide visibility into accuracy, throughput, and exceptions.

## 4-Phase Roadmap
1. **Quick Wins**: Central "Order Register" with real-time status tracking and basic deduplication.
2. **AI-Assisted Order Capture**: LLM extraction, SKU matching engine, and structured payload generation.
3. **Customer Self-Service**: Web/LINE OA interface for order status, confirmations, and corrections.
4. **Advanced Analytics**: SLA monitoring, exception trends, and forecasting for labor/capacity planning.

## Demo Architecture Overview
The demo centers on four key functions, showing how they interact end-to-end.

### 1) Unified Entry
- **Input**: Centralized Order Register via LINE OA or a lightweight web app.
- **Action**: Aggregates unstructured requests (chat, email paste, uploads) into a single stream.
- **Output**: Real-time order status tracking with request IDs and timestamps.

### 2) Automated Extraction
- **Tech**: LLM models + prompt templates tuned for purchase orders, delivery orders, and invoices.
- **Action**: Extracts intent, quantities, client metadata, delivery dates, and references.
- **Feature**: **SKU Matching Engine** standardizes product codes using fuzzy matching and master data normalization.

### 3) Intelligent Validation
- **Logic**: AI mapping against Master Product Data, price lists, and credit/shipping rules.
- **Control**: **HITL interface** surfaces low-confidence extractions for review with side-by-side source vs. parsed fields.
- **Result**: Verified **Golden Record** of the order with provenance for each field.

### 4) Execute & Sync
- **Action**: Automated entry into ERP (Oracle) through APIs or RPA fallback.
- **Loop**: Trigger "follow-up logic" for customer confirmation (via LINE OA push or email) and internal alerts.
- **Result**: Order finalized, with confirmation artifacts linked back to the Golden Record.

## Demo Flow (Sample Scenario)
1. Customer sends a purchase order PDF through LINE OA.
2. Order Register stores the request and invokes the extraction pipeline.
3. LLM extracts items, quantities, incoterms, and customer metadata; SKU Matching Engine maps items to master SKUs.
4. Validation layer checks prices/credit and flags low-confidence fields for HITL review.
5. Reviewer confirms or corrects flagged fields; system emits a Golden Record.
6. ERP sync creates sales order and schedules delivery; customer receives confirmation and can view status.
7. Delivery order and invoice events update the same record for traceability.

## Data Model (Golden Record)
- **Order Header**: order_id, customer_id, channel, request_timestamp, promised_date, status, confidence_score.
- **Line Items**: sku_id, source_description, normalized_description, quantity, unit_price, currency, uom, confidence.
- **Attachments**: source_files (purchase order, delivery order, invoice), parsed text, and extraction provenance.
- **Audit Trail**: HITL decisions, ERP sync status, follow-up communications.

## AI Components
- **Extraction**: prompt templates per document type; structured JSON output with confidence per field.
- **SKU Matching**: vector similarity over normalized descriptions, rule-based synonyms, and hard validations against master product data.
- **Validation Rules**: permissible UOMs, price bands, credit limits, ship-to/bill-to checks.
- **Confidence Scoring**: combined signals from model certainty, SKU match distance, and rule compliance.

## HITL Experience
- **Queue**: prioritized by confidence and business impact.
- **Review UI**: side-by-side source (PDF/JPEG/text) and parsed fields with inline edit.
- **Actions**: approve, correct, split/merge lines, map to SKU, and re-run validation.
- **Outcome**: updated Golden Record, with rationale captured for analytics.

## Integration Points
- **Inbound**: LINE OA webhook, web form uploads, or email ingest.
- **Core**: Order Register API (REST/GraphQL) to create/update Golden Records.
- **Outbound**: Oracle ERP sales order API, delivery confirmation callbacks, invoice posting.
- **Notifications**: LINE OA push, email, or webhook to customer systems.

## Metrics to Showcase in the Demo
- Extraction accuracy by field (header vs. lines).
- HITL volume and turnaround time.
- Duplicate/ambiguous SKU rate and resolution time.
- End-to-end lead time: intake → validation → ERP sync.
- Exception categories (missing data, price/credit blocks, SKU mismatches).

## Quick Win Implementation Checklist
- [x] Stand up Order Register service with request logging and status tracking (see `quick_win_demo.py`).
- [x] Add lightweight extraction for purchase orders (regex-based, JSON output with confidence scores).
- [x] Implement SKU Matching Engine against sample master product data (`data/master_products.json`).
- [ ] Build minimal HITL review page for low-confidence lines.
- [ ] Connect to Oracle ERP sandbox API (or mock) for order creation.
- [ ] Enable customer confirmation push message and link to status page.

### Quick Win Demo (offline)
The repo includes a small offline demo that simulates the **Order Register + Extraction + SKU Matching + Validation** loop.

**Run the demo**

```bash
# 1) (Optional) Create a virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 2) Install dependencies (standard library only; no packages to install)
python -c "import json, pathlib; print('ready')"

# 3) Execute the demo
# CLI output + HTML dashboard (default)
python quick_win_demo.py

# Skip writing HTML
python quick_win_demo.py --no-html
```

After running the default command, open the generated **`quick_win_dashboard.html`** in your browser to share a static snapshot of the results. The CLI output shows the matched SKUs and validation notes for each sample order.

**What it shows**

- Deduplicated request IDs per customer/message.
- Regex-based extraction of line items (quantity + description) from unstructured chat/email text.
- SKU matching against the sample master catalog with a simple confidence score.
- Validation notes when the match confidence is low or missing (mimicking HITL flags).
- A dashboard-style snapshot of the Golden Records for the ingested requests (also rendered as HTML).

**Sample catalog**

- `data/master_products.json` contains three SKUs with synonyms to demonstrate normalization and fuzzy overlap.

## Demo Assets (suggested)
- Sample master product catalog (CSV/JSON) with synonyms and UOM mappings.
- Sample documents: purchase order, delivery order, and invoice PDFs.
- Postman collection for Order Register API and ERP sync callbacks.
- Slides showing architecture, roadmap, and impact metrics.

## Expected Impact
- **Reduced manual effort**: fewer touchpoints and re-keying.
- **Improved accuracy**: standardized SKUs and validation rules cut errors.
- **Better customer experience**: clear confirmations and status visibility.
- **Enables scale**: automation absorbs volume growth without linear headcount.

