# CLI Contract: wiki_merger.py

## Invocation

```
python src/wiki_merger.py <command> [options]
```

## Commands

### `detect`

Scan all wiki pages and report duplicate groups. No files are modified.

```
python src/wiki_merger.py detect
```

**Output format:**

```
=== Same-Domain Near-Duplicates ===

[behavioral-economics]
  KEEP  a-logica-do-consumo-verdades-e-mentiras   (conf=0.95)
  MERGE a-logica-do-consumo-verdades-e-mentiras-  (conf=0.92)

[psychology]
  KEEP  as-consequencias-vem-depois   (conf=0.88)
  MERGE as-consequencias-vem--depois  (conf=0.79)

=== Cross-Domain Slug Groups ===

[antifragilidade]
  KEEP  mental-model  (conf=0.90)
  MERGE market        (conf=0.85)
  MERGE philosophy    (conf=0.82)
  MERGE psychology    (conf=0.80)
  MERGE theology      (conf=0.78)

...

Summary: 2 same-domain pairs, 8 cross-domain groups
```

---

### `merge`

Merge two or more specific pages. The canonical is determined automatically (or overridden with `--keep`).

```
python src/wiki_merger.py merge FILE1 FILE2 [FILE3 ...]
python src/wiki_merger.py merge FILE1 FILE2 --keep FILE1   # force FILE1 as canonical
python src/wiki_merger.py merge FILE1 FILE2 --dry-run
```

**Options:**

| Option | Description |
|--------|-------------|
| `--keep PATH` | Force a specific file as the canonical (override auto-selection) |
| `--dry-run` | Print old and new content, write nothing |

**Output:**

```
[MERGE] a-logica-do-consumo-verdades-e-mentiras (behavioral-economics)
  canonical: .../a-logica-do-consumo-verdades-e-mentiras.md
  deleting:  .../a-logica-do-consumo-verdades-e-mentiras-.md
  sources: 1 → 2 (merged)
  links:   2 → 7 (merged)
  body: consolidated via LLM
[DONE]
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | All specified pages merged successfully |
| 1 | One or more pages failed or were skipped |
| 2 | Invalid arguments or file not found |

---

### `batch`

Detect all groups and merge them all. Same-domain pairs are processed first, then cross-domain groups.

```
python src/wiki_merger.py batch
python src/wiki_merger.py batch --dry-run
```

**Options:**

| Option | Description |
|--------|-------------|
| `--dry-run` | Print all proposed changes, write nothing |

**Output:**

```
=== Processing Same-Domain Pairs ===
[MERGE] as-consequencias-vem-depois (psychology) ... [DONE]
[MERGE] a-logica-do-consumo-verdades-e-mentiras (behavioral-economics) ... [DONE]

=== Processing Cross-Domain Groups ===
[MERGE] antifragilidade → mental-model ... [DONE]
[MERGE] resolucao-de-problemas → mental-model ... [DONE]
...

Summary:
  Same-domain:  2 found, 2 merged, 0 skipped, 0 errored
  Cross-domain: 8 found, 8 merged, 0 skipped, 0 errored
```
