# Adversarial review contract

Review only risk classes that are relevant to the artifact. Do not manufacture findings to fill categories.

Prioritize exploitable or decision-relevant issues by: Critical, High, Medium, Low.
For each finding include evidence, impact, likelihood/exploit preconditions, and a specific remediation.

For software, consider as applicable: authorization, authentication, injection, secrets, data exposure, dependency/supply-chain risk, prompt injection/tool abuse, unsafe deserialization, SSRF, XSS/CSRF, race conditions, availability, observability, rollback, cost, performance, scalability, and maintainability.

End with a remediation order optimized for risk reduction per unit effort. Distinguish verified findings from hypotheses requiring validation.
