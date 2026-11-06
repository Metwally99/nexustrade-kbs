// =============================================================================
//  NexusTrade — Knowledge Base Schema
// =============================================================================
//  Defines the structural contract of the rule graph: node uniqueness
//  constraints and lookup indexes. Run this ONCE against an empty database
//  before loading data with `seed_rules.cypher`.
//
//  Graph schema:
//    (:Domain    {name, display_name})
//    (:Rule      {rule_id, description, action, action_key, action_value,
//                 priority, entity_type, entity_pattern})
//    (:Condition {fact_pattern, operator, threshold, description})
//
//    (:Rule)-[:IN_DOMAIN]->(:Domain)
//    (:Rule)-[:HAS_CONDITION {order}]->(:Condition)
//
//  Usage:
//    cypher-shell -u neo4j -p <password> -f schema.cypher
// =============================================================================


// ── Uniqueness constraints ───────────────────────────────────────────────────
//  rule_id  — every rule must have a unique identifier (R1, R2, …, R25)
//  domain.name — every domain (pricing, inventory, …) appears exactly once

CREATE CONSTRAINT rule_id_unique     IF NOT EXISTS FOR (r:Rule)   REQUIRE r.rule_id IS UNIQUE;
CREATE CONSTRAINT domain_name_unique IF NOT EXISTS FOR (d:Domain) REQUIRE d.name    IS UNIQUE;


// ── Lookup indexes ───────────────────────────────────────────────────────────
//  fact_pattern — supports "which rules depend on fact X?" queries used by
//                 the explanation facility and by rule-impact analysis.
//  Condition has no natural unique key (the same fact_pattern + operator +
//  threshold can legitimately appear in multiple rules), so we index, not
//  constrain.

CREATE INDEX condition_fact_pattern IF NOT EXISTS FOR (c:Condition) ON (c.fact_pattern);
