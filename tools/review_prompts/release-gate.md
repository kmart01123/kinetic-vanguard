Review this pull request as an independent exact-head reviewer.

Focus on concrete correctness, security, reproducibility, regressions, and
maintainability defects that could materially affect operation. Inspect the actual
pull request diff and relevant surrounding code.

Do not report stylistic preferences or request broad redesign without a concrete
defect. Classify concrete defects that should stop merge as BLOCKER, HIGH, or
MEDIUM. Classify non-blocking hardening, usability, or future-maintenance
observations as LOW.

Do not repeat findings already disproven by the current code or execution evidence
unless the current exact head provides new concrete evidence.

Complete the inspection before returning one final review. Do not return progress
reports, placeholders, "review in progress", "being processed", or promises of
later findings. If there are no concrete findings, return verdict PASS with
`findings = []`. If there are concrete findings, return verdict FINDINGS with at
least one structured finding; never return FINDINGS with an empty findings array.
If the review cannot be completed in this invocation, fail instead of emitting a
placeholder.
