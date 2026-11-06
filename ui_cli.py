"""
NexusTrade — CLI Interface
=========================
Main command-line interface for interacting with the KBS.
Supports:
  1. Business selection (choose e-commerce preset)
  2. Automatic diagnosis (forward chaining)
  3. Goal-driven queries (backward chaining)
  4. ERP data browsing
  5. Explanation facility
"""

import sys
from erp_module import MockERP, get_available_businesses
from knowledge_base import KnowledgeBase
from inference_engine import ForwardChainer, BackwardChainer
from explanation import ExplanationEngine


class NexusTradeCLI:
    """Interactive CLI for NexusTrade."""

    def __init__(self):
        self.erp = None
        self.kb = KnowledgeBase()
        self.explainer = ExplanationEngine()
        self.fc = None
        self.bc = None

    def run(self):
        """Main loop."""
        self._print_banner()
        self._select_business()       # Let user choose business first
        self._run_forward_chaining()

        while True:
            self._print_menu()
            choice = input("\n  Enter choice (1-8): ").strip()

            if choice == "1":
                self._select_business()
                self._run_forward_chaining()
            elif choice == "2":
                self._run_forward_chaining()
            elif choice == "3":
                self._run_backward_chaining()
            elif choice == "4":
                self._show_erp_data()
            elif choice == "5":
                self._show_rules()
            elif choice == "6":
                self._explain_rule()
            elif choice == "7":
                self._show_full_report()
            elif choice == "8":
                print("\n  👋 Goodbye from NexusTrade!\n")
                sys.exit(0)
            else:
                print("\n  ⚠️  Invalid choice. Try again.")

    def _print_banner(self):
        print()
        print("╔" + "═" * 58 + "╗")
        print("║" + " " * 9 + "NexusTrade — Knowledge-Based System" + " " * 14 + "║")
        print("║" + " " * 6 + "ERP-Integrated E-Commerce Decision Support" + " " * 9 + "║")
        print("╚" + "═" * 58 + "╝")

    def _select_business(self):
        """Let user choose which e-commerce business to analyze."""
        businesses = get_available_businesses()
        keys = list(businesses.keys())

        print("\n" + "═" * 60)
        print("  🏬 Select E-Commerce Business to Analyze")
        print("═" * 60)
        for i, key in enumerate(keys, 1):
            biz = businesses[key]
            print(f"  {i}. {biz['icon']} {biz['name']}")
            print(f"     {biz['description']}")
            print()

        while True:
            choice = input(f"  Choose business (1-{len(keys)}): ").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(keys):
                    selected_key = keys[idx]
                    break
                else:
                    print(f"  ⚠️  Enter a number between 1 and {len(keys)}.")
            except ValueError:
                print(f"  ⚠️  Enter a number between 1 and {len(keys)}.")

        biz = businesses[selected_key]
        if self.erp is None:
            self.erp = MockERP(selected_key)
        else:
            self.erp.switch_business(selected_key)
        self.fc = None  # reset diagnosis
        print(f"\n  ✅ Loaded: {biz['icon']} {biz['name']}")
        print(f"     {biz['description']}")

    def _print_menu(self):
        biz_name = f"{self.erp.business_icon} {self.erp.business_name}" if self.erp else "No business selected"
        print(f"\n{'─' * 50}")
        print(f"  MAIN MENU  │  {biz_name}")
        print("─" * 50)
        print("  1  Switch business")
        print("  2  Run forward chaining (auto diagnosis)")
        print("  3  Run backward chaining (goal query)")
        print("  4  Browse ERP data")
        print("  5  View all rules")
        print("  6  Explain a specific rule")
        print("  7  Show full business health report")
        print("  8  Exit")

    def _run_forward_chaining(self):
        print("\n" + "═" * 60)
        print("  🔄 Running Forward Chaining — Automatic Diagnosis")
        print("═" * 60)

        self.fc = ForwardChainer(self.kb, self.erp)
        results = self.fc.run()

        report = self.explainer.generate_full_report(self.fc.trace)
        print(report)

    def _run_backward_chaining(self):
        print("\n" + "═" * 60)
        print("  🎯 Backward Chaining — Goal-Driven Query")
        print("═" * 60)

        print("\n  Available goal types:")
        print("  ─────────────────────")
        print("  • recommendation_P001_clearance_discount")
        print("  • recommendation_P002_standard_reorder")
        print("  • recommendation_P002_urgent_reorder")
        print("  • customer_C001_segment")
        print("  • diagnosis_P001_declining_sales")
        print("  • recommendation_S002_blacklist")
        print()
        print("  Format: <type>_<entity_id>_<conclusion>")
        print("  Products: P001-P005 | Customers: C001-C008 | Suppliers: S001-S005")

        goal = input("\n  Enter your goal: ").strip()
        if not goal:
            print("  ⚠️  No goal entered.")
            return

        self.bc = BackwardChainer(self.kb, self.erp)
        success, trace = self.bc.run(goal)

        if trace:
            for entry in trace:
                explanation = self.explainer.explain_conclusion(entry)
                print(explanation)

    def _show_erp_data(self):
        self.erp.print_summary()

    def _show_rules(self):
        print("\n  Select domain (or 'all'):")
        print("  1. pricing    2. inventory    3. customer")
        print("  4. supplier   5. sales        6. all")

        choice = input("\n  Choice: ").strip()
        domain_map = {"1": "pricing", "2": "inventory", "3": "customer",
                       "4": "supplier", "5": "sales", "6": None}
        domain = domain_map.get(choice)
        if choice not in domain_map:
            print("  ⚠️  Invalid choice.")
            return
        self.kb.print_rules(domain)

    def _explain_rule(self):
        rule_id = input("\n  Enter rule ID (e.g. R1, R15): ").strip().upper()
        rule = self.kb.get_rule(rule_id)
        if not rule:
            print(f"  ⚠️  Rule {rule_id} not found.")
            return

        print(f"\n{'━' * 60}")
        print(f"  Rule [{rule.rule_id}]")
        print(f"{'━' * 60}")
        print(f"  Domain      : {rule.domain}")
        print(f"  Description : {rule.description}")
        print(f"  Priority    : {rule.priority}/10")
        print(f"  Action      : {rule.action}")
        print(f"\n  Conditions:")
        for i, c in enumerate(rule.conditions, 1):
            print(f"    {i}. {c.description}")
            print(f"       Fact: {c.fact_pattern} {c.operator} {c.threshold}")

        if self.fc:
            fired_for = []
            for entry in self.fc.trace:
                if entry.rule.rule_id == rule_id and entry.fired:
                    fired_for.append(entry)
            if fired_for:
                print(f"\n  📌 This rule FIRED in the last diagnosis for:")
                for entry in fired_for:
                    print(f"     → {entry.result}")
                    evidence = self.explainer.explain_evidence(entry)
                    print(evidence)
            else:
                print(f"\n  ℹ️  This rule did NOT fire in the last diagnosis.")

        print(f"{'━' * 60}")

    def _show_full_report(self):
        if not self.fc:
            print("\n  ⚠️  Run forward chaining first (option 2).")
            return
        report = self.explainer.generate_full_report(self.fc.trace)
        print(report)

        ask = input("\n  Show detailed explanations? (y/n): ").strip().lower()
        if ask == 'y':
            for entry in self.fc.trace:
                if entry.fired:
                    print(self.explainer.explain_conclusion(entry))
                    print(self.explainer.explain_evidence(entry))


if __name__ == "__main__":
    cli = NexusTradeCLI()
    cli.run()
