"""Quick win demo for AI-assisted order-to-cash workflow.

This script simulates a minimal Order Register with basic extraction,
SKU matching, and validation to create a "Golden Record" from
unstructured order messages. It uses a small sample catalog and
messages to illustrate the quick win phase before a full LLM pipeline.
"""
from __future__ import annotations

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


def run_demo():
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


if __name__ == "__main__":
    run_demo()
