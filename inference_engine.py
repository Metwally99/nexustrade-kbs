"""
NexusTrade — Inference Engine
============================
Hybrid inference engine with two strategies:

  ForwardChainer  — Data-driven: loads all ERP facts, scans every rule,
                    fires all whose conditions are met.  Produces an
                    instant business health report.

  BackwardChainer — Goal-driven: starts from a user goal (e.g. "Should I
                    reorder P002?"), works backward to find which rules
                    and facts are needed, asks the user only for missing
                    facts.

Both engines produce a full reasoning trace consumed by the Explanation
facility.
"""

from typing import List, Dict, Any, Tuple, Callable, Optional
import re
from knowledge_base import KnowledgeBase, Rule, Condition
from erp_module import MockERP


# ── Reasoning Trace Entry ────────────────────────────────────────────────────

class TraceEntry:
    """One step in the reasoning trace."""

    def __init__(self, rule: Rule, bindings: Dict[str, str],
                 matched_facts: Dict[str, Any], result: str, fired: bool):
        self.rule = rule
        self.bindings = bindings
        self.matched_facts = matched_facts    # fact_key → value
        self.result = result                  # action text
        self.fired = fired                    # did the rule fire?

    def __repr__(self):
        status = "FIRED" if self.fired else "NOT FIRED"
        return f"<Trace [{self.rule.rule_id}] {status}: {self.result}>"


# ── Forward Chainer ──────────────────────────────────────────────────────────

class ForwardChainer:
    """
    Data-driven reasoning.  Loads facts → scans rules → fires matches.
    Repeats until no new facts are derived (fixed-point).
    """

    def __init__(self, kb: KnowledgeBase, erp: MockERP):
        self.kb = kb
        self.erp = erp
        self.facts: Dict[str, Any] = {}
        self.trace: List[TraceEntry] = []
        self.fired_rules: List[Tuple[Rule, Dict[str, str], str]] = []

    def run(self) -> List[Tuple[Rule, Dict[str, str], str]]:
        """Execute forward chaining. Returns list of (rule, bindings, action)."""
        self.facts = self.erp.extract_facts()
        self.trace = []
        self.fired_rules = []

        # We may do multiple passes since some rules (e.g. R3) depend on
        # facts produced by other rules (e.g. R11 sets customer_segment = VIP).
        max_iterations = 5
        # Sort by priority desc so when multiple rules share an `action_key`
        # (e.g. R11–R14 all write customer_{cid}_segment), the highest-priority
        # match wins regardless of rule_id ordering in the source. Without
        # this, the chainer would silently honor load order, not priority.
        ordered_rules = sorted(self.kb.get_all_rules(),
                               key=lambda r: r.priority, reverse=True)
        for iteration in range(max_iterations):
            new_facts_added = False
            for rule in ordered_rules:
                # Find all entity instances this rule can bind to
                bindings_list = self._find_all_bindings(rule)
                for bindings in bindings_list:
                    action_key = rule.get_action_key_resolved(bindings)
                    # Skip if already fired for this binding
                    if action_key and action_key in self.facts:
                        continue

                    if self._evaluate_rule(rule, bindings):
                        action_text = rule.get_action_text(bindings)
                        matched = self._get_matched_facts(rule, bindings)
                        entry = TraceEntry(rule, bindings, matched, action_text, True)
                        self.trace.append(entry)
                        self.fired_rules.append((rule, bindings, action_text))

                        # Assert new fact
                        if action_key:
                            self.facts[action_key] = rule.action_value
                            new_facts_added = True

            if not new_facts_added:
                break

        return self.fired_rules

    def _find_all_bindings(self, rule: Rule) -> List[Dict[str, str]]:
        """Find all possible variable bindings for a rule."""
        bindings_list = []

        if rule.entity_type == "product":
            for p in self.erp.get_all_products():
                binding = {"pid": p.product_id}
                # Some rules also need supplier bindings
                if any("{sid}" in c.fact_pattern for c in rule.conditions):
                    for s in self.erp.get_suppliers_for_product(p.product_id):
                        b = {**binding, "sid": s.supplier_id}
                        bindings_list.append(b)
                else:
                    bindings_list.append(binding)

        elif rule.entity_type == "customer":
            for c in self.erp.get_all_customers():
                bindings_list.append({"cid": c.customer_id})

        elif rule.entity_type == "supplier":
            for s in self.erp.get_all_suppliers():
                binding = {"sid": s.supplier_id}
                if any("{pid}" in c.fact_pattern for c in rule.conditions):
                    binding["pid"] = s.product_id
                bindings_list.append(binding)

        else:
            bindings_list.append({})

        return bindings_list

    def _evaluate_rule(self, rule: Rule, bindings: Dict[str, str]) -> bool:
        """Evaluate all conditions of a rule with dynamic threshold support."""
        for cond in rule.conditions:
            fact_key = cond.get_fact_key(bindings)

            if fact_key not in self.facts:
                return False

            value = self.facts[fact_key]
            threshold = cond.threshold

            # Handle dynamic thresholds (comparing against another fact)
            if isinstance(threshold, str) and threshold.startswith("DYNAMIC:"):
                dynamic_key = threshold[8:]  # strip "DYNAMIC:"
                # Resolve bindings in dynamic key
                for var, val in bindings.items():
                    dynamic_key = dynamic_key.replace(f"{{{var}}}", val)

                # Special case: reorder_point_x2
                if dynamic_key.endswith("_x2"):
                    base_key = dynamic_key[:-3]
                    if base_key not in self.facts:
                        return False
                    threshold = self.facts[base_key] * 2
                else:
                    if dynamic_key not in self.facts:
                        return False
                    threshold = self.facts[dynamic_key]

            if not Condition._compare(value, cond.operator, threshold):
                return False

        return True

    def _get_matched_facts(self, rule: Rule, bindings: Dict[str, str]) -> Dict[str, Any]:
        """Collect the actual fact values used in rule evaluation."""
        matched = {}
        for cond in rule.conditions:
            key = cond.get_fact_key(bindings)
            if key in self.facts:
                matched[key] = self.facts[key]
            # Also include dynamic threshold source
            if isinstance(cond.threshold, str) and cond.threshold.startswith("DYNAMIC:"):
                dynamic_key = cond.threshold[8:]
                for var, val in bindings.items():
                    dynamic_key = dynamic_key.replace(f"{{{var}}}", val)
                if dynamic_key.endswith("_x2"):
                    base_key = dynamic_key[:-3]
                    if base_key in self.facts:
                        matched[base_key] = self.facts[base_key]
                elif dynamic_key in self.facts:
                    matched[dynamic_key] = self.facts[dynamic_key]
        return matched

    def get_results_by_domain(self) -> Dict[str, List[Tuple[Rule, Dict[str, str], str]]]:
        """Group fired rules by domain."""
        grouped: Dict[str, List] = {}
        for rule, bindings, action in self.fired_rules:
            grouped.setdefault(rule.domain, []).append((rule, bindings, action))
        return grouped


# ── Backward Chainer ─────────────────────────────────────────────────────────

class BackwardChainer:
    """
    Goal-driven reasoning.  Starts from a hypothesis and works backward
    to determine if the facts support it.
    """

    def __init__(self, kb: KnowledgeBase, erp: MockERP,
                 ask_user: Callable[[str], Any] = None):
        self.kb = kb
        self.erp = erp
        self.facts: Dict[str, Any] = {}
        self.trace: List[TraceEntry] = []
        self.ask_user = ask_user or self._default_ask
        self.asked_facts: Dict[str, Any] = {}

    def run(self, goal: str) -> Tuple[bool, List[TraceEntry]]:
        """
        Attempt to prove a goal.
        Returns (success, trace).
        """
        self.facts = self.erp.extract_facts()
        self.trace = []
        self.asked_facts = {}

        # Find rules that can conclude this goal
        rules = self.kb.get_rules_for_goal(goal)

        if not rules:
            print(f"\n  ❌ No rules found that can conclude: {goal}")
            return False, self.trace

        for rule in sorted(rules, key=lambda r: r.priority, reverse=True):
            bindings = self.kb.extract_bindings(rule, goal)
            if bindings is None:
                continue

            print(f"\n  🔍 Trying rule [{rule.rule_id}]: {rule.description}")

            success = self._prove_rule(rule, bindings)
            action_text = rule.get_action_text(bindings)
            matched = self._get_matched_facts(rule, bindings)
            entry = TraceEntry(rule, bindings, matched, action_text, success)
            self.trace.append(entry)

            if success:
                # Assert the conclusion
                self.facts[goal] = rule.action_value
                print(f"\n  ✅ Goal proved via [{rule.rule_id}]: {action_text}")
                return True, self.trace

        print(f"\n  ❌ Could not prove goal: {goal}")
        return False, self.trace

    def _prove_rule(self, rule: Rule, bindings: Dict[str, str]) -> bool:
        """Try to satisfy all conditions of a rule."""
        for cond in rule.conditions:
            fact_key = cond.get_fact_key(bindings)
            threshold = cond.threshold

            # Resolve dynamic thresholds
            actual_threshold = threshold
            if isinstance(threshold, str) and threshold.startswith("DYNAMIC:"):
                dynamic_key = threshold[8:]
                for var, val in bindings.items():
                    dynamic_key = dynamic_key.replace(f"{{{var}}}", val)
                if dynamic_key.endswith("_x2"):
                    base_key = dynamic_key[:-3]
                    if base_key in self.facts:
                        actual_threshold = self.facts[base_key] * 2
                    else:
                        actual_threshold = self._ask_for_fact(base_key, cond.description)
                        if actual_threshold is not None:
                            actual_threshold = actual_threshold * 2
                        else:
                            return False
                else:
                    if dynamic_key in self.facts:
                        actual_threshold = self.facts[dynamic_key]
                    else:
                        actual_threshold = self._ask_for_fact(dynamic_key, cond.description)
                        if actual_threshold is None:
                            return False

            # Check if fact exists
            if fact_key not in self.facts:
                # Ask user for the missing fact
                value = self._ask_for_fact(fact_key, cond.description)
                if value is None:
                    return False
                self.facts[fact_key] = value

            value = self.facts[fact_key]
            if not Condition._compare(value, cond.operator, actual_threshold):
                print(f"    ✗ Condition failed: {cond.description}")
                print(f"      {fact_key} = {value} (need {cond.operator} {actual_threshold})")
                return False
            else:
                print(f"    ✓ Condition met: {cond.description}")
                print(f"      {fact_key} = {value} {cond.operator} {actual_threshold}")

        return True

    def _ask_for_fact(self, fact_key: str, description: str) -> Any:
        """Ask user for a missing fact."""
        if fact_key in self.asked_facts:
            return self.asked_facts[fact_key]

        print(f"\n  ❓ Need fact: {fact_key}")
        print(f"     Why: {description}")
        value = self.ask_user(fact_key)
        if value is not None:
            self.asked_facts[fact_key] = value
            self.facts[fact_key] = value
        return value

    def _get_matched_facts(self, rule: Rule, bindings: Dict[str, str]) -> Dict[str, Any]:
        """Collect the actual fact values used in evaluation."""
        matched = {}
        for cond in rule.conditions:
            key = cond.get_fact_key(bindings)
            if key in self.facts:
                matched[key] = self.facts[key]
        return matched

    @staticmethod
    def _default_ask(fact_key: str) -> Any:
        """Default: ask via CLI input."""
        try:
            raw = input(f"     Enter value for '{fact_key}' (or 'skip'): ").strip()
            if raw.lower() == 'skip':
                return None
            # Try to parse as number
            try:
                if '.' in raw:
                    return float(raw)
                return int(raw)
            except ValueError:
                # Boolean
                if raw.lower() in ('true', 'yes'):
                    return True
                if raw.lower() in ('false', 'no'):
                    return False
                return raw
        except (EOFError, KeyboardInterrupt):
            return None


# ── Convenience: run both engines ────────────────────────────────────────────

def run_full_diagnosis(erp: MockERP = None, kb: KnowledgeBase = None):
    """Run forward chaining and return structured results."""
    erp = erp or MockERP()
    kb = kb or KnowledgeBase()
    fc = ForwardChainer(kb, erp)
    results = fc.run()
    return fc


# ── Quick test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    erp = MockERP()
    kb = KnowledgeBase()

    print("=" * 70)
    print("  NexusTrade — Forward Chaining (Automatic Diagnosis)")
    print("=" * 70)

    fc = ForwardChainer(kb, erp)
    results = fc.run()

    by_domain = fc.get_results_by_domain()
    domain_labels = {
        "pricing": "💰 Pricing & Discounts",
        "inventory": "📦 Inventory Reorder",
        "customer": "👥 Customer Segmentation",
        "supplier": "🏭 Supplier & Procurement",
        "sales": "📊 Sales Performance",
    }

    for domain, label in domain_labels.items():
        entries = by_domain.get(domain, [])
        print(f"\n{label}")
        print("-" * 60)
        if not entries:
            print("  No issues detected.")
        for rule, bindings, action in entries:
            print(f"  [{rule.rule_id}] {action}")

    print(f"\n\nTotal rules fired: {len(results)}")
