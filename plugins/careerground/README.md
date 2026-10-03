# CareerGround plugin source

`plugin.json` and `skills/career-interview/SKILL.md` are the portable source package.
The source has no default external endpoint or account credentials. Bind it to a
reviewed MCP endpoint or an already registered private test server when building:

```bash
uv run python scripts/build_chatgpt_plugin.py \
  --output /tmp/careerground-plugin.zip \
  --registered-server-id asdk_app_REPLACE_WITH_OBSERVED_ID
```

Use the exact server ID observed in the registered plugin's downloaded `.app.json`.
The `plugin_asdk_app_...` page route is a UI wrapper; the server mapping uses the
actual `asdk_app_...` ID. Do not guess a mapping or overwrite an existing archive.
`--mcp-url` is an alternative for an explicitly reviewed HTTPS resource endpoint.
Without either option the archive is skills-only and still needs a CareerGround
MCP connection to perform data actions.

The builder includes only the manifest, this actual skill, and the explicit MCP
binding. Repository `.env`, test database credentials, drafts and private stores
are excluded. It performs no installation, external request or publication.

## Private synthetic ChatGPT trial

```bash
uv run python -m careerground.chatgpt_synthetic_trial \
  --port 8044 --allow-synthetic-chatgpt-tunnel
```

The trial listens only on `127.0.0.1`, owns a disposable SQLite database and keys,
and accepts the private development tunnel at `/chatgpt/mcp`. Its outer connection
uses a fixed synthetic identity with no end-user OAuth; the inner product MCP
still validates a minted synthetic JWT and its permissions. Use only an approved
workspace-associated Secure MCP Tunnel. A public forwarding service is outside
this trial's scope. It is unsuitable for real data or real account authentication.

Ask ChatGPT to initialize an empty synthetic profile, then open
`http://127.0.0.1:8044/chatgpt` to select the same synthetic account in the management
browser. The browser and ChatGPT have separate sessions/credentials. Follow the
server's exact confirmation link, then return to the originating conversation.
Stopping the trial removes the disposable store; the existing development store
and old OAuth PoC remain separate.

This test covers model/tool behavior. Production registration still needs a
trusted verified-identity adapter, stable enrollment admission IDs that survive
revocation/erasure, real browser session binding and the external identity gates.

Small browser-approved exports (up to 64 KiB UTF-8) arrive in the export tool's
`content` with `content_delivery=INLINE`. Larger results have
`content_delivery=RESOURCE_ONLY` and no truncated body. A host that supports MCP
resources can refresh its list and read the exact private `resource_uri` on the
same credential. Resource metadata completion alone does not verify the body.
