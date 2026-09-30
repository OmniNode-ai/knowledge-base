---
type: guide
status: current
date: "2026-09-30"
title: "Supported Platforms"
topics: [install, platforms, macos, intel, quickstart]
refs: []
---

# Supported Platforms

Where the `onex` command-line tool installs, and how. The install path depends on your
computer, not on which quickstart you follow.

| Platform | How it installs | Prebuilt wheels |
|----------|-----------------|-----------------|
| macOS on Apple Silicon (M1 and newer) | `uv tool install`, nothing extra | Yes |
| Linux, x86_64 | `uv tool install`, nothing extra | Yes |
| Linux, arm64 | `uv tool install`, nothing extra | Yes |
| macOS on Intel | **Built from source**: extra prerequisites, follow the section below | No |
| Windows | Not tested | Not applicable |

"Prebuilt wheels" matters because one required dependency, `cryptography` (version 50 or newer,
held there on purpose to stay ahead of published security advisories), ships no macOS x86_64
wheel. On an Intel Mac `uv` therefore compiles it, and that build needs a Rust toolchain and the
OpenSSL headers. Without them the install fails deep inside the compiler with a message like
`Could not find directory of OpenSSL installation`. Nothing else in the tool differs on Intel.

Check which machine you have: `uname -sm` prints `Darwin arm64` on Apple Silicon and
`Darwin x86_64` on Intel. If it prints `x86_64` on a Mac you know is Apple Silicon, your
terminal is running under Rosetta; open a native terminal instead, and the wheels install
normally.

## Intel macOS: build from source

You need three things, all from Homebrew (install [Homebrew](https://brew.sh) first if you
do not have it, which also installs Apple's command line tools):

```bash
brew install openssl@3 rust uv
```

Then point the build at that OpenSSL and install as usual, in the same terminal window:

```bash
export OPENSSL_DIR="$(brew --prefix openssl@3)"
uv tool install --with 'omnibase-infra>=0.38.4' --with 'omnimarket>=0.4.205' 'omnibase-core>=0.46.8'
```

The first install compiles `cryptography` and takes several minutes longer than on other
platforms; later installs and upgrades reuse the result. It ends with the same `Installed`
line described in the [quickstart](onex-plugin-quickstart.md), and `onex --version` works.

The `install.sh` installer detects an Intel Mac before it clones or installs anything. It
prints this path, checks for the three prerequisites, sets `OPENSSL_DIR` for you, and stops
with the exact `brew` command for anything missing.

If you would rather not build from source, run the same install inside a Linux container.
The steps are identical to the Linux path.

## Support is tested

A scheduled install check installs the tool into an empty home directory on Linux, on Apple
Silicon macOS, and on Intel macOS using exactly the Intel steps above, then runs a delegation
against a stub model. If a change breaks one of these paths, that check fails.
