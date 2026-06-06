# Security Policy

## Supported Versions

The `main` branch and the latest tagged release are the supported targets for
security fixes. If a report affects an older commit, please include the commit
SHA and the closest tagged release in the report.

## Reporting a Vulnerability

Please do not open a public issue for suspected vulnerabilities.

Send a private report through GitHub's security advisory flow if it is enabled
for this repository, or contact the maintainer through the public GitHub profile
for `Chedrian07` and include:

- affected version or commit SHA
- steps to reproduce
- expected and actual impact
- any logs, payloads, or proof-of-concept files needed to reproduce the issue

I will acknowledge confirmed reports as soon as practical and coordinate a fix
before public disclosure.

## Security-Sensitive Areas

Reports are especially useful for:

- API key or secret exposure in the CLI, web UI, logs, caches, or run artifacts
- sandbox escapes or unsafe defaults in code-execution benchmarks
- local web UI authentication, bind-token, or origin handling issues
- provider adapter bugs that could send requests to an unintended endpoint
- dependency, packaging, or Docker image vulnerabilities

## Scope

This policy covers the llm-evalbox source code, packaging, Docker workflow,
local web UI, evaluation runner, cache handling, and benchmark sandbox logic.
Upstream benchmark datasets and third-party model/provider behavior should be
reported to their respective maintainers unless llm-evalbox introduces the
vulnerability.
