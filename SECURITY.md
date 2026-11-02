# Security

Report suspected vulnerabilities through this repository's **Security > Report a vulnerability**
private reporting flow. Avoid posting credentials, Steam userdata or exploit details affecting
other users in public issues. Ordinary installation/uninstall questions belong in Issues.

CS2Kit configures a Wine bottle and processes local files. Download verification, safe archive
handling, generated scripts, prefix ownership and data-preserving filesystem operations are security
boundaries. It never needs Steam credentials or administrator privileges to run its Python CLI.

The supported runtime is Python 3.9 or newer with no third-party runtime dependencies. CI exercises
3.9, 3.13 and 3.14 on Linux and macOS. See [the CI and security policy](docs/project/ci-security.md)
for checks, threat boundaries and the expiring compatibility exception in the test toolchain.

Game, Wine, DXMT and macOS vulnerabilities remain upstream responsibilities. A passing scanner or
integrity baseline does not certify downloaded native code or establish VAC acceptance.
