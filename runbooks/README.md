# Runbooks

Operational procedures — bring-up, rollout, diagnosis, recovery — written so that someone operating the platform can follow them under pressure. The distinguishing test is that the reader is trying to **operate or recover** something.

## Every runbook here is parameterized

Runbooks are the documents most likely to have been written against a real environment, and therefore the most likely to carry a real address, hostname, or home directory path. Nothing published here carries one. Use the placeholder tokens defined in [docs-taxonomy.md](../docs-taxonomy.md): `<onex-host>`, `<kafka-bootstrap-servers>`, `<runner-home>`, `<repo-root>`, `<cluster-ip>`.

Where a procedure genuinely needs a real value to be operable, the value belongs in a restricted operational note and the published runbook stays parameterized. "It has to be real to be useful" is the reasoning that put addresses in public documentation in the first place.

Scrubbing is also not the whole test. A fully parameterized runbook can still disclose operational controls or failure-mode internals that are sensitive independent of any literal address. Those documents are restricted, and restricted documents are blocked from publication rather than routed here — see the taxonomy's ordered decision rule.

## This section is open

Frontmatter `type: runbook`, with `status: draft | current | stale | deprecated`. The validator discovers files recursively and the sanitization guard scans every runbook regardless of nesting depth — see [docs-taxonomy.md](../docs-taxonomy.md) for what belongs here, and [migration-manifest.yaml](../migration-manifest.yaml) for the planned mapping.
