# Security model

Threats covered: prompt injection, tool privilege escalation, secret exfiltration, unsafe production writes, confused-deputy behavior, malicious retrieved documents, over-broad MCP permissions, and trace leakage.

Controls:
- default-deny policy engine;
- explicit approval class distinct from allow/deny;
- trust tagging for tool-call provenance;
- injection inspection for untrusted retrieved text;
- secret-read/export denial by default;
- production DB/deploy/IAM/billing approval gates;
- trace minimization and no-secret logging rule;
- independent red-team findings must contain evidence.

Non-goals: this package does not replace cloud IAM, network isolation, secret managers, sandboxing, database permissions, or human approval UX. Those controls must enforce the same policy independently.
