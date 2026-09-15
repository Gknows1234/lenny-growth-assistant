# Security policy

Do not include API keys, `.env` files, customer prompts, private transcripts, database exports, or raw production
logs in issues. Report vulnerabilities privately to the repository owner before public disclosure.

The current release is a local evaluation build. The `X-User-Id` browser header provides session partitioning,
not authentication. Do not expose this application to untrusted networks until verified identity, TLS, production
secrets, database network policy, data retention, abuse controls, and monitoring are in place.

Generated HTML is sanitized and sandboxed, but dependency and browser security updates remain required. Treat a
bypass of the sanitizer/CSP/iframe boundary as high severity.

