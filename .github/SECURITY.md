# Security policy

This fork of [Puppetboard](https://github.com/voxpupuli/puppetboard) adds a
read-only JSON API and an MCP server. Both read your whole Puppet
inventory and have no authentication of their own; how to run them safely
is described in [docs/API.md](https://github.com/DennisPohlmann/puppetboard/blob/main/docs/API.md#securing-api-and-mcp).

## Supported versions

| Version | Supported |
|---|---|
| `main` | yes, fixes land here |
| anything older | no, please update |

## Reporting a vulnerability

Please **do not open a public issue, discussion or pull request** for a
vulnerability.

Report it privately on GitHub: **Security** tab of the repository,
**Report a vulnerability**
([direct link](https://github.com/DennisPohlmann/puppetboard/security/advisories/new)).

Helpful to include:

- the commit or image you run and how (container or gunicorn),
  with the settings that matter (`ENABLE_API`, `ENABLE_MCP`,
  `ENABLE_QUERY`, `MCP_ALLOWED_HOSTS`, `OFFLINE_MODE`);
- the steps to reproduce, and what an attacker gains;
- whether you plan to publish it, and when.

Never include real certnames, facts, reports, certificates or keys of your
infrastructure; made-up values from a test PuppetDB are enough.

A problem that also exists in upstream Puppetboard (the web interface
without API and MCP) is best reported to
[voxpupuli/puppetboard](https://github.com/voxpupuli/puppetboard/security)
as well.

## What happens next

- You get an answer within **7 days**.
- The problem is confirmed or explained, and a fix is planned together
  with you. The aim is a fix on `main` within **90 days**, much sooner for a
  problem that exposes data or lets a client change anything in PuppetDB.
- The advisory is published with the fix, with credit to you unless you
  prefer not to be named.

## In scope

Everything in this repository: the web interface, the JSON API under
`/api/v1/`, the MCP server under `/mcp`, the container image and the
bundled JavaScript. Especially anything that writes to PuppetDB, reads
data past the documented limits, bypasses input checks, rate limit or the
Host check of `/mcp`, leaks PuppetDB internals, or injects script into a
page.

Out of scope: missing authentication on `/api/v1/` and `/mcp` (by design,
it belongs in the reverse proxy), problems that need a changed server, and
scanner findings without a way to exploit them in Puppetboard (those are
welcome as a normal issue).
