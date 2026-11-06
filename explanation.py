"""
NexusTrade — Explanation Facility
================================
Every conclusion is traced and explained:

  "Why are you asking this?"
      → cites which rule needs this fact

  "How did you reach this conclusion?"
      → prints the full rule chain that fired

  "What evidence supported it?"
      → shows the ERP values that matched each condition
"""

from typing import List, Dict, Any, Tuple
from knowledge_base import Rule
from inference_engine import TraceEntry


class ExplanationEngine:
    """Generates human-readable explanations from reasoning traces."""

    def __init__(self):
        self.log: List[str] = []

    def clear(self):
        self.log = []

    # ── Why was this question asked? ─────────────────────────────────────

    def explain_why_asked(self, rule: Rule, fact_key: str,
                          condition_desc: str) -> str:
        """Explain why a specific fact was requested during backward chaining."""
        explanation = (
            f"\n{'─' * 60}\n"
            f"  ❓ WHY WAS THIS ASKED?\n"
            f"{'─' * 60}\n"
            f"  Fact needed : {fact_key}\n"
            f"  Required by : Rule [{rule.rule_id}] — {rule.description}\n"
            f"  Reason      : {condition_desc}\n"
            f"  Domain      : {rule.domain}\n"
            f"{'─' * 60}"
        )
        self.log.append(explanation)
        return explanation

    # ── How was this conclusion reached? ─────────────────────────────────

    def explain_conclusion(self, trace_entry: TraceEntry) -> str:
        """Explain the full rule chain for a single fired rule."""
        r = trace_entry.rule
        b = trace_entry.bindings

        explanation = (
            f"\n{'━' * 60}\n"
            f"  🔎 HOW WAS THIS CONCLUSION REACHED?\n"
            f"{'━' * 60}\n"
            f"  Rule        : [{r.rule_id}] {r.description}\n"
            f"  Domain      : {r.domain}\n"
            f"  Priority    : {r.priority}/10\n"
            f"  Conclusion  : {trace_entry.result}\n"
            f"  Status      : {'✅ FIRED' if trace_entry.fired else '❌ NOT FIRED'}\n"
        )

        if trace_entry.bindings:
            explanation += f"  Bindings    : {trace_entry.bindings}\n"

        # Conditions detail
        explanation += f"\n  📋 CONDITIONS EVALUATED:\n"
        for i, cond in enumerate(r.conditions, 1):
            fact_key = cond.get_fact_key(b)
            actual_val = trace_entry.matched_facts.get(fact_key, "N/A")
            threshold = cond.threshold
            if isinstance(threshold, str) and threshold.startswith("DYNAMIC:"):
                dyn_key = threshold[8:]
                for var, val in b.items():
                    dyn_key = dyn_key.replace(f"{{{var}}}", val)
                if dyn_key.endswith("_x2"):
                    base_key = dyn_key[:-3]
                    base_val = trace_entry.matched_facts.get(base_key, "?")
                    threshold_display = f"2 × {base_key} = {base_val * 2 if isinstance(base_val, (int, float)) else '?'}"
                else:
                    dyn_val = trace_entry.matched_facts.get(dyn_key, "?")
                    threshold_display = f"{dyn_key} = {dyn_val}"
            else:
                threshold_display = threshold

            explanation += (
                f"    {i}. {cond.description}\n"
                f"       {fact_key} = {actual_val} {cond.operator} {threshold_display}\n"
            )

        explanation += f"{'━' * 60}"
        self.log.append(explanation)
        return explanation

    # ── What evidence supported it? ──────────────────────────────────────

    def explain_evidence(self, trace_entry: TraceEntry) -> str:
        """Show the raw ERP data values that matched each condition."""
        explanation = (
            f"\n{'─' * 60}\n"
            f"  📊 SUPPORTING EVIDENCE\n"
            f"{'─' * 60}\n"
            f"  Rule: [{trace_entry.rule.rule_id}] {trace_entry.rule.description}\n\n"
        )

        for key, value in trace_entry.matched_facts.items():
            explanation += f"    • {key} = {value}\n"

        if not trace_entry.matched_facts:
            explanation += "    (no matching facts recorded)\n"

        explanation += f"{'─' * 60}"
        self.log.append(explanation)
        return explanation

    # ── Full Report for Forward Chaining ─────────────────────────────────

    def generate_full_report(self, trace: List[TraceEntry]) -> str:
        """Generate a comprehensive report from forward chaining trace."""
        fired = [t for t in trace if t.fired]

        report = (
            f"\n{'═' * 60}\n"
            f"  NexusTrade — BUSINESS HEALTH REPORT\n"
            f"{'═' * 60}\n"
            f"  Total rules evaluated : {len(trace)}\n"
            f"  Rules fired           : {len(fired)}\n"
        )

        # Group by domain
        by_domain: Dict[str, List[TraceEntry]] = {}
        for t in fired:
            by_domain.setdefault(t.rule.domain, []).append(t)

        domain_labels = {
            "pricing": "💰 PRICING & DISCOUNTS",
            "inventory": "📦 INVENTORY REORDER",
            "customer": "👥 CUSTOMER SEGMENTATION",
            "supplier": "🏭 SUPPLIER & PROCUREMENT",
            "sales": "📊 SALES PERFORMANCE",
        }

        for domain in ["pricing", "inventory", "customer", "supplier", "sales"]:
            entries = by_domain.get(domain, [])
            label = domain_labels.get(domain, domain.upper())
            report += f"\n  {label}\n"
            report += f"  {'─' * 50}\n"
            if not entries:
                report += "    ✅ No issues detected\n"
            else:
                for t in entries:
                    report += f"    [{t.rule.rule_id}] {t.result}\n"

        report += f"\n{'═' * 60}\n"
        self.log.append(report)
        return report

    # ── Export log ───────────────────────────────────────────────────────

    def get_full_log(self) -> str:
        return "\n".join(self.log)

    def get_trace_data(self, trace: List[TraceEntry]) -> List[Dict[str, Any]]:
        """Convert trace to structured data (for web UI)."""
        data = []
        for t in trace:
            conditions_data = []
            for cond in t.rule.conditions:
                fact_key = cond.get_fact_key(t.bindings)
                actual = t.matched_facts.get(fact_key, None)
                conditions_data.append({
                    "description": cond.description,
                    "fact_key": fact_key,
                    "operator": cond.operator,
                    "threshold": cond.threshold,
                    "actual_value": actual,
                })

            data.append({
                "rule_id": t.rule.rule_id,
                "domain": t.rule.domain,
                "description": t.rule.description,
                "action": t.result,
                "fired": t.fired,
                "priority": t.rule.priority,
                "bindings": t.bindings,
                "conditions": conditions_data,
                "evidence": t.matched_facts,
            })
        return data
