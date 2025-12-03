"""Quick win demo for AI-assisted order-to-cash workflow.

This script simulates a minimal Order Register with basic extraction,
SKU matching, and validation to create a "Golden Record" from
unstructured order messages. It uses a small sample catalog and
messages to illustrate the quick win phase before a full LLM pipeline.

Pass ``--html <path>`` to export an embeddable HTML dashboard that
anyone can open without running Python.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

CATALOG_PATH = Path("data/master_products.json")


def load_catalog(path: Path) -> List[Dict]:
    with path.open() as f:
        return json.load(f)


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


@dataclass
class OrderLine:
    source_description: str
    quantity: int
    matched_sku: Optional[str] = None
    normalized_description: Optional[str] = None
    confidence: float = 0.0


@dataclass
class GoldenRecord:
    request_id: str
    customer: str
    channel: str
    status: str
    lines: List[OrderLine] = field(default_factory=list)
    validation_notes: List[str] = field(default_factory=list)

    def summary(self) -> Dict:
        return {
            "request_id": self.request_id,
            "customer": self.customer,
            "channel": self.channel,
            "status": self.status,
            "lines": [
                {
                    "source_description": line.source_description,
                    "quantity": line.quantity,
                    "matched_sku": line.matched_sku,
                    "confidence": round(line.confidence, 2),
                }
                for line in self.lines
            ],
            "validation_notes": self.validation_notes,
        }


class SKUMatcher:
    def __init__(self, catalog: Iterable[Dict]):
        self.catalog = list(catalog)

    def match(self, description: str) -> Tuple[Optional[str], float]:
        text = normalized(description)
        best_score = 0.0
        best_sku = None
        for item in self.catalog:
            candidates = [item["name"], *item.get("synonyms", [])]
            for alias in candidates:
                alias_norm = normalized(alias)
                if alias_norm in text or text in alias_norm:
                    score = 0.9
                else:
                    score = self._token_overlap(alias_norm, text)
                if score > best_score:
                    best_score = score
                    best_sku = item["sku_id"]
        return best_sku, best_score

    @staticmethod
    def _token_overlap(a: str, b: str) -> float:
        a_tokens, b_tokens = set(a.split()), set(b.split())
        if not a_tokens or not b_tokens:
            return 0.0
        overlap = len(a_tokens & b_tokens) / len(a_tokens | b_tokens)
        return overlap


class QuickWinPipeline:
    def __init__(self, catalog_path: Path = CATALOG_PATH):
        self.catalog = load_catalog(catalog_path)
        self.matcher = SKUMatcher(self.catalog)
        self.register: Dict[str, GoldenRecord] = {}

    def ingest(self, message: str, customer: str, channel: str = "LINE OA") -> GoldenRecord:
        request_id = self._generate_id(message, customer)
        record = GoldenRecord(
            request_id=request_id,
            customer=customer,
            channel=channel,
            status="received",
        )
        record.lines = self._extract_lines(message)
        record.status = "extracted"
        self._match_and_validate(record)
        self.register[request_id] = record
        return record

    def _generate_id(self, message: str, customer: str) -> str:
        digest = hashlib.sha1(f"{customer}-{message}".encode()).hexdigest()[:8]
        return f"REQ-{digest}"

    def _extract_lines(self, message: str) -> List[OrderLine]:
        lines = []
        pattern = re.compile(r"(?P<qty>\d+)x?\s+(?P<item>[A-Za-z0-9 \-\.\"']+)")
        for match in pattern.finditer(message):
            qty = int(match.group("qty"))
            item = match.group("item").strip()
            lines.append(OrderLine(source_description=item, quantity=qty))
        if not lines:
            # fallback: treat whole message as one line with qty 1
            lines.append(OrderLine(source_description=message.strip(), quantity=1, confidence=0.1))
        return lines

    def _match_and_validate(self, record: GoldenRecord) -> None:
        for line in record.lines:
            sku, score = self.matcher.match(line.source_description)
            line.matched_sku = sku
            line.confidence = score
            line.normalized_description = normalized(line.source_description)
            if not sku:
                record.validation_notes.append(
                    f"No SKU match for '{line.source_description}' (qty {line.quantity})"
                )
            elif score < 0.5:
                record.validation_notes.append(
                    f"Low confidence ({score:.2f}) match for '{line.source_description}' -> {sku}"
                )
        record.status = "validated" if not record.validation_notes else "needs_review"

    def dashboard(self) -> List[Dict]:
        return [rec.summary() for rec in self.register.values()]


def demo_messages() -> List[Dict[str, str]]:
    return [
        {
            "customer": "Acme Steel",
            "channel": "LINE OA",
            "message": "Need 2x PVC pipe 2in and 5 copper cable 1.5 for Monday",
        },
        {
            "customer": "Bright Energy",
            "channel": "Email",
            "message": "Order: 3 pcs 8p switch, 50m 1.5mm wire",
        },
        {
            "customer": "Acme Steel",
            "channel": "LINE OA",
            "message": "repeat last order of 2\" pvc",
        },
    ]


def render_html_dashboard(records: List[Dict]) -> str:
    rows = []
    for rec in records:
        lines_html = "".join(
            f"<li><strong>{line['quantity']}×</strong> {line['source_description']}"
            f" → <code>{line['matched_sku'] or '—'}</code>"
            f" <span class='chip'>{line['confidence']:.2f}</span></li>"
            for line in rec["lines"]
        )
        notes_html = (
            "".join(f"<li>{note}</li>" for note in rec["validation_notes"])
            or "<li>None</li>"
        )
        rows.append(
            f"""
<article class='card'>
  <header>
    <div>
      <div class='label'>Request ID</div>
      <div class='value'>{rec['request_id']}</div>
    </div>
    <div>
      <div class='label'>Customer</div>
      <div class='value'>{rec['customer']}</div>
    </div>
    <div>
      <div class='label'>Channel</div>
      <div class='value'>{rec['channel']}</div>
    </div>
    <div class='status {rec['status']}'>{rec['status']}</div>
  </header>
  <div class='section'>
    <div class='section-title'>Line items</div>
    <ul class='list'>
      {lines_html}
    </ul>
  </div>
  <div class='section'>
    <div class='section-title'>Validation notes</div>
    <ul class='list notes'>
      {notes_html}
    </ul>
  </div>
</article>
"""
        )

    return f"""
<!doctype html>
<html lang='en'>
<head>
  <meta charset='UTF-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1.0'/>
  <title>Quick Win Demo Dashboard</title>
  <style>
    :root {{
      --bg: #0f172a;
      --card: #111827;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --accent: #3b82f6;
      --warning: #f97316;
      --border: #1f2937;
    }}
    body {{
      margin: 0;
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      background: radial-gradient(circle at 10% 20%, #1e293b 0, #0f172a 25%),
                  radial-gradient(circle at 80% 0, #0b2345 0, #0f172a 35%),
                  #0f172a;
      color: var(--text);
    }}
    .page {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 40px 24px 64px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 32px;
      letter-spacing: -0.02em;
    }}
    .subtitle {{ color: var(--muted); margin-bottom: 24px; }}
    .grid {{
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
    }}
    header {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      align-items: center;
      margin-bottom: 12px;
    }}
    .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
    .value {{ font-weight: 600; }}
    .status {{
      justify-self: end;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border: 1px solid var(--border);
      background: rgba(59, 130, 246, 0.12);
      color: var(--text);
    }}
    .status.needs_review {{ background: rgba(249, 115, 22, 0.18); color: #fb923c; }}
    .section {{ margin-top: 10px; }}
    .section-title {{ color: var(--muted); font-size: 13px; margin-bottom: 6px; }}
    .list {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 6px; }}
    .list li {{
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 12px;
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
    }}
    .list.notes li {{ color: var(--muted); font-size: 13px; }}
    .chip {{
      margin-left: auto;
      padding: 4px 8px;
      border-radius: 999px;
      background: rgba(59, 130, 246, 0.16);
      font-size: 12px;
      color: #bfdbfe;
      border: 1px solid rgba(59, 130, 246, 0.35);
    }}
    code {{ background: rgba(255, 255, 255, 0.05); padding: 2px 6px; border-radius: 6px; }}
  </style>
</head>
<body>
  <div class='page'>
    <h1>Quick Win Demo Dashboard</h1>
    <div class='subtitle'>Golden Records created from the sample Order Register.</div>
    <div class='grid'>
      {''.join(rows)}
    </div>
  </div>
</body>
</html>
"""


def run_demo(html_path: Optional[Path] = None):
    pipeline = QuickWinPipeline()
    print("=== Quick Win Demo ===")
    for payload in demo_messages():
        record = pipeline.ingest(payload["message"], payload["customer"], payload["channel"])
        print(f"\nRequest {record.request_id} from {record.customer} via {record.channel}")
        print(f"Status: {record.status}")
        for line in record.lines:
            sku_display = line.matched_sku or "<no match>"
            print(
                f"  - {line.quantity} x {line.source_description} -> {sku_display} "
                f"(confidence {line.confidence:.2f})"
            )
        if record.validation_notes:
            print("  Validation notes:")
            for note in record.validation_notes:
                print(f"    * {note}")
    print("\nDashboard snapshot:")
    for rec in pipeline.dashboard():
        print(json.dumps(rec, indent=2))

    if html_path:
        records = pipeline.dashboard()
        html_path.write_text(render_html_dashboard(records))
        print(f"\nSaved HTML dashboard to {html_path.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quick win order register demo")
    parser.add_argument(
        "--html",
        type=Path,
        default=Path("quick_win_dashboard.html"),
        help="Path to save an HTML dashboard of the demo output.",
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Skip writing the HTML dashboard.",
    )
    args = parser.parse_args()

    run_demo(html_path=None if args.no_html else args.html)
