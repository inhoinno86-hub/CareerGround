# Canonical profile export foundation (synthetic only)

The internal `export_profile_data` path creates a bounded JSON string in memory from one exact archived profile version. A caller must provide an explicit integer version or `CURRENT`; ownership and active account/profile state are checked by the archive reader. Missing, erased, cross-account, or corrupted versions fail without falling back to the latest state.

The JSON contains active Claim wording and its three-axis assessment, fact-review state, applicable constraints, selected Evidence excerpts and original input references/hashes. It also includes active standalone boundaries, including scopes with no accepted Claim. Each source is labeled `SELECTED_EXCERPT_ONLY`; expired full conversation text is never reconstructed. The caller may verify the SHA-256 hash of the deterministic JSON. Requests for temporary drafts or expired source bodies are rejected until a separate retention-aware inclusion policy exists.

This is a canonical-only projection. It does not create an export artifact, authorized download resource, public MCP/web command, or include temporary drafts and all historical review rows. It is not a complete portability endpoint. No real account or operational service is connected.
