"""
NexusTrade — Knowledge Base
==========================
Holds the 25 IF-THEN rules across 5 decision domains:
  1. Pricing & Discounts      (R1–R5)
  2. Inventory Reorder         (R6–R10)
  3. Customer Segmentation     (R11–R15)
  4. Supplier & Procurement    (R16–R20)
  5. Sales Performance         (R21–R25)

Rules are stored in Neo4j (Aura) and loaded at startup. The graph schema
and seed data are defined in `schema.cypher` and `seed_rules.cypher`. Run
those files once against the Aura instance before starting the app.

Each rule is materialized in memory as a `Rule` dataclass with:
  - rule_id, domain, description
  - conditions: list of Condition objects
  - action: the conclusion / recommendation text (with {pid}/{cid}/{sid})
  - priority: for conflict resolution
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Any, Callable, Dict, Optional
import re
import os
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

try:
    from Database.config import Config
except ImportError:
    Config = None


# ── Rule Model ───────────────────────────────────────────────────────────────

@dataclass
class Condition:
    """A single condition that references a fact pattern."""
    fact_pattern: str        # e.g. "product_{pid}_stock_vs_avg_sales_pct"
    operator: str            # ">", "<", ">=", "<=", "==", "!="
    threshold: Any           # value to compare against
    description: str = ""    # human‑readable description

    def evaluate(self, facts: Dict[str, Any], bindings: Dict[str, str] = None) -> bool:
        """Evaluate this condition against a set of facts."""
        key = self._resolve_key(bindings)
        if key not in facts:
            return False
        value = facts[key]
        return self._compare(value, self.operator, self.threshold)

    def get_fact_key(self, bindings: Dict[str, str] = None) -> str:
        return self._resolve_key(bindings)

    def _resolve_key(self, bindings: Dict[str, str] = None) -> str:
        key = self.fact_pattern
        if bindings:
            for var, val in bindings.items():
                key = key.replace(f"{{{var}}}", val)
        return key

    @staticmethod
    def _compare(value, operator: str, threshold) -> bool:
        ops = {
            ">":  lambda a, b: a > b,
            "<":  lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
        }
        if operator not in ops:
            raise ValueError(f"Unknown operator: {operator}")
        return ops[operator](value, threshold)


@dataclass
class Rule:
    """A single IF-THEN rule."""
    rule_id: str
    domain: str
    description: str
    conditions: List[Condition]
    action: str                   # textual conclusion / recommendation
    action_key: str = ""          # fact key to assert (for forward chaining)
    action_value: Any = True      # value to assert
    priority: int = 5             # 1 = low, 10 = high
    entity_type: str = ""         # "product", "customer", "supplier", "sales"
    entity_pattern: str = ""      # regex to extract entity from fact keys

    def get_required_facts(self, bindings: Dict[str, str] = None) -> List[str]:
        """Return list of fact keys needed to evaluate this rule."""
        return [c.get_fact_key(bindings) for c in self.conditions]

    def evaluate(self, facts: Dict[str, Any], bindings: Dict[str, str] = None) -> bool:
        """Return True if ALL conditions are met."""
        return all(c.evaluate(facts, bindings) for c in self.conditions)

    def get_action_text(self, bindings: Dict[str, str] = None) -> str:
        """Return action text with bindings resolved."""
        text = self.action
        if bindings:
            for var, val in bindings.items():
                text = text.replace(f"{{{var}}}", val)
        return text

    def get_action_key_resolved(self, bindings: Dict[str, str] = None) -> str:
        key = self.action_key
        if bindings:
            for var, val in bindings.items():
                key = key.replace(f"{{{var}}}", val)
        return key


# ── Knowledge Base ───────────────────────────────────────────────────────────

class KnowledgeBase:
    """
    Loads all rules from Neo4j into memory at startup, then serves them
    from the in-memory list. Rules are immutable for the lifetime of the
    KB instance — re-instantiate to pick up edits made in Neo4j.
    """

    def __init__(self,
                 uri: Optional[str]      = None,
                 user: Optional[str]     = None,
                 password: Optional[str] = None,
                 database: Optional[str] = None):
        self.rules: List[Rule] = []

        # Resolve credentials: explicit args > Config (.env) > env vars > defaults
        self._uri      = uri      or (Config.NEO4J_URI      if Config else None) or os.getenv("NEO4J_URI")
        self._user     = user     or (Config.NEO4J_USER     if Config else None) or os.getenv("NEO4J_USER", "neo4j")
        self._password = password or (Config.NEO4J_PASSWORD if Config else None) or os.getenv("NEO4J_PASSWORD")
        self._database = database or (Config.NEO4J_DATABASE if Config else None) or os.getenv("NEO4J_DATABASE", "neo4j")

        if not self._uri or not self._password:
            raise RuntimeError(
                "Neo4j credentials missing. Set NEO4J_URI and NEO4J_PASSWORD "
                "in your .env file (see .env for placeholders)."
            )

        self._driver = GraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )
        self._load_rules()

    def close(self):
        """Close the Neo4j driver. Optional — driver is also closed at GC."""
        if getattr(self, "_driver", None):
            self._driver.close()
            self._driver = None

    def get_all_rules(self) -> List[Rule]:
        return self.rules

    def get_rules_by_domain(self, domain: str) -> List[Rule]:
        return [r for r in self.rules if r.domain == domain]

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        return next((r for r in self.rules if r.rule_id == rule_id), None)

    def get_rules_for_goal(self, goal_key: str) -> List[Rule]:
        """Find rules whose action_key matches a goal (backward chaining)."""
        results = []
        for r in self.rules:
            # Check if the rule's action key pattern could match the goal
            pattern = r.action_key
            if not pattern:
                continue
            # Convert {pid}, {cid}, {sid} placeholders to regex
            regex = pattern.replace("{pid}", r"[\w]+")
            regex = regex.replace("{cid}", r"[\w]+")
            regex = regex.replace("{sid}", r"[\w]+")
            regex = f"^{regex}$"
            if re.match(regex, goal_key):
                results.append(r)
        return results

    def extract_bindings(self, rule: Rule, goal_key: str) -> Optional[Dict[str, str]]:
        """Extract variable bindings from a goal key matching a rule's action key."""
        pattern = rule.action_key
        if not pattern:
            return None
        # Build regex with named groups
        regex = pattern
        for var in ["pid", "cid", "sid"]:
            regex = regex.replace(f"{{{var}}}", f"(?P<{var}>[\\w]+)")
        regex = f"^{regex}$"
        match = re.match(regex, goal_key)
        if match:
            return match.groupdict()
        return None

    # ── Rule Loading from Neo4j ──────────────────────────────────────────

    _LOAD_QUERY = """
    MATCH (r:Rule)-[:IN_DOMAIN]->(d:Domain)
    OPTIONAL MATCH (r)-[h:HAS_CONDITION]->(c:Condition)
    WITH r, d, c, h
    ORDER BY r.rule_id, h.order
    RETURN r.rule_id        AS rule_id,
           d.name           AS domain,
           r.description    AS description,
           r.action         AS action,
           r.action_key     AS action_key,
           r.action_value   AS action_value,
           r.priority       AS priority,
           r.entity_type    AS entity_type,
           r.entity_pattern AS entity_pattern,
           collect({
               fact_pattern: c.fact_pattern,
               operator:     c.operator,
               threshold:    c.threshold,
               description:  c.description,
               order:        h.order
           }) AS conditions
    ORDER BY r.rule_id
    """

    def _load_rules(self):
        """Load all rules from Neo4j into self.rules."""
        try:
            with self._driver.session(database=self._database) as session:
                records = list(session.run(self._LOAD_QUERY))
        except AuthError as e:
            raise RuntimeError(
                f"Neo4j authentication failed: {e}. Check NEO4J_USER / NEO4J_PASSWORD."
            ) from e
        except ServiceUnavailable as e:
            raise RuntimeError(
                f"Cannot reach Neo4j at {self._uri}. If using Aura free tier, "
                f"the instance may be paused — open it in console.neo4j.io to resume."
            ) from e

        # Sort rule_ids naturally so R2 < R10 (otherwise lexical "R10" < "R2")
        records.sort(key=lambda rec: (rec["rule_id"][0], int(rec["rule_id"][1:])))

        for rec in records:
            raw_conditions = sorted(
                (c for c in rec["conditions"] if c["fact_pattern"] is not None),
                key=lambda c: c["order"] if c["order"] is not None else 0,
            )
            conditions = [
                Condition(
                    fact_pattern = c["fact_pattern"],
                    operator     = c["operator"],
                    threshold    = c["threshold"],
                    description  = c["description"] or "",
                )
                for c in raw_conditions
            ]
            self.rules.append(Rule(
                rule_id        = rec["rule_id"],
                domain         = rec["domain"],
                description    = rec["description"] or "",
                conditions     = conditions,
                action         = rec["action"] or "",
                action_key     = rec["action_key"] or "",
                action_value   = rec["action_value"],
                priority       = rec["priority"] if rec["priority"] is not None else 5,
                entity_type    = rec["entity_type"] or "",
                entity_pattern = rec["entity_pattern"] or "",
            ))

        if not self.rules:
            raise RuntimeError(
                "Neo4j returned 0 rules. Did you run schema.cypher and "
                "seed_rules.cypher against this database?"
            )

    def print_rules(self, domain: str = None):
        """Pretty-print rules, optionally filtered by domain."""
        rules = self.get_rules_by_domain(domain) if domain else self.rules
        domains_seen = set()
        for r in rules:
            if r.domain not in domains_seen:
                domains_seen.add(r.domain)
                domain_names = {
                    "pricing": "💰 Pricing & Discounts",
                    "inventory": "📦 Inventory Reorder",
                    "customer": "👥 Customer Segmentation",
                    "supplier": "🏭 Supplier & Procurement",
                    "sales": "📊 Sales Performance Diagnosis",
                }
                print(f"\n{'=' * 70}")
                print(f"  {domain_names.get(r.domain, r.domain)}")
                print(f"{'=' * 70}")
            print(f"\n  [{r.rule_id}] {r.description}")
            print(f"       → {r.action}")
            print(f"       Priority: {r.priority}/10")


# ── Quick test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    kb = KnowledgeBase()
    try:
        kb.print_rules()
        print(f"\n\nTotal rules loaded from Neo4j: {len(kb.rules)}")
    finally:
        kb.close()
