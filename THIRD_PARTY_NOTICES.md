# Third-Party Notices

This project's `pricing.json` incorporates data normalized from the following
open-source projects. We acknowledge their work and license terms here.

## BerriAI/litellm — MIT License

Source: https://github.com/BerriAI/litellm

Specifically, we consume the file:
`model_prices_and_context_window.json`

via `scrapers/litellm_source.py`. Model IDs, context window sizes, and per-token
prices are derived from this catalog and normalized into our schema.

litellm is licensed under the MIT License. A copy of its license is reproduced
in the litellm repository. The use here complies with that license's attribution
requirement.

`pricing.json` itself also carries a top-level `attribution` field pointing back
to litellm at runtime.
