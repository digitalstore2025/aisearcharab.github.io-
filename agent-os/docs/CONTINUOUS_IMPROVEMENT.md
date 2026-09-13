# Continuous improvement loop

1. Capture production trace/failure without secrets.
2. Cluster the failure by cause: routing, retrieval, policy, tool use, reasoning, stale context, completion, or external dependency.
3. Reproduce it as a deterministic eval when possible.
4. Change the smallest responsible component: skill description, prompt, policy, router, retrieval, model tier, or code.
5. Run the complete regression suite.
6. Canary the change on a small traffic slice or offline replay set.
7. Promote only if success improves without unacceptable safety/cost/latency regression.

Do not fix every model failure by adding more prompt text.
