# CareerGround

Evidence-backed Career AI System

## Current status

Career Graph v1 domain/schema validation and Career Profiling Protocol v1.
Three synthetic fixtures cover feature ownership, supporting contribution and
team/process leadership. Application services are not implemented.

## Core documents

- [Career Graph Entity/Relationship Model v1](docs/career_graph_entity_relationship_model_v1.md)
- [Career Graph Schema v1](docs/career_graph_schema_v1.md)
- [Career Graph Schema Validation](docs/career_graph_schema_v1_validation.md)
- [Career Profiling Protocol v1](docs/career_profiling_protocol_v1.md)

## Core principle

Every career claim should be traceable to evidence. User confirmation, external
verification and permission to publish are separate decisions. Interview discoveries
remain candidates until explicit review; ownership wording must respect its scope.

## Run validation

Python 3, standard library only (verified with Python 3.14.4):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The tests validate synthetic fixtures and a small reference model for publication,
candidate promotion and historical traceability. They do not verify real careers,
run a database, implement authentication or validate a complete JSON Schema.
See the validation report for coverage, negative cases and open decisions.
