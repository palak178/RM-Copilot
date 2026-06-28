"""Domain layer — pure business entities and value objects. NO I/O.

Holds the types from docs/data-model.md §2: Customer, Product, ProductHolding,
Transaction, Interaction (durable entities) and the derived value objects
(Assessment, FactorContribution, Trigger, EligibilityResult, Recommendation,
OutreachMessage, ExecutionEvent).

Rules:
- No imports from data/, services/, tools/, agent/, or any third-party I/O lib.
- Money is represented as integer paise (never float).
- Enums mirror the CHECK-constrained values in docs/data-model.md §4.

Implemented (M1): enums, the five durable entities, and money helpers. Derived
value objects (Assessment, Recommendation, ...) arrive with the services in M2.
"""
