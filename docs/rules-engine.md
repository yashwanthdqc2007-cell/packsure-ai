# PackSure AI — Rules Engine

The deterministic rules engine applies the Legal Metrology (Packaged Commodities) Rules, 2011 to extracted declarations.

## Principle

AI extracts. Rules engine decides.

## Rule Structure

Each rule will define:
- `rule_code` — Official rule reference (e.g., Rule 6(1)(a))
- `field_name` — Which declaration field it validates
- `validation_type` — presence | format | range | conditional
- `severity` — critical | major | minor

## TODO

- Populate rules.json after legal research is complete
- Implement validators per field type
- Implement product-category-based rule selection
- Handle conditional rules (e.g., expiry only required for certain product types)
