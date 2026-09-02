---
type: reference
status: current
date: "2026-09-02"
title: "Validation Performance Notes"
topics: [omnibase-infra, validation, performance, notes]
refs: []
---

<!-- Migrated from omnibase_infra:docs/validation/performance_notes.md on 2026-09-02. -->

# Validation Performance Notes

Performance considerations and optimization strategies for ONEX infrastructure validation.

## Performance Overview

Validation performance characteristics for omnibase_infra (as of v0.1.0):

| Validator | Complexity | Typical Runtime | Bottleneck |
|-----------|-----------|-----------------|------------|
| Architecture | O(n) | 50-200ms | File I/O, AST parsing |
| Contracts | O(n) | 100-300ms | YAML parsing |
| Patterns | O(n) | 50-200ms | AST analysis |
| Union Usage | O(n) | 50-200ms | Type annotation parsing |
| Circular Imports | O(n²) | 200-1000ms | Dependency graph analysis |

**Total Runtime** (all validators): **450-1900ms** for typical infrastructure codebase

**Note**: Performance scales with:
- Number of Python files
- Codebase complexity
- Dependency graph depth

## Performance Characteristics

### 1. Architecture Validator

**Algorithm**: Linear file scan with AST parsing

**Time Complexity**: O(n) where n = number of Python files

**Performance Profile**:
```
File Discovery:    10-20ms  (os.walk)
AST Parsing:      30-150ms  (ast.parse per file)
Model Detection:   10-30ms  (AST node traversal)
Total:            50-200ms
```

**Optimization Strategies**:

1. **Incremental Validation**: Only validate changed files
   ```python
   # Get changed files from git
   changed_files = get_git_changed_files()

   # Validate only changed files
   for file in changed_files:
       validate_single_file(file)
   ```

2. **Parallel Processing**: Use multiprocessing for large codebases
   ```python
   from concurrent.futures import ProcessPoolExecutor

   with ProcessPoolExecutor() as executor:
       results = executor.map(validate_file, python_files)
   ```

3. **Caching**: Cache AST parse results for unchanged files
   ```python
   ast_cache = {}
   if file_hash in ast_cache:
       tree = ast_cache[file_hash]
   else:
       tree = ast.parse(file_content)
       ast_cache[file_hash] = tree
   ```

### 2. Contract Validator

**Algorithm**: Linear YAML file parsing

**Time Complexity**: O(n) where n = number of contract YAML files

**Performance Profile**:
```
File Discovery:    10-20ms  (glob pattern matching)
YAML Parsing:     80-250ms  (yaml.safe_load per file)
Schema Validation: 10-30ms  (contract schema checks)
Total:           100-300ms
```

**Optimization Strategies**:

1. **Lazy Loading**: Parse contracts only when needed
   ```python
   # Don't parse all contracts upfront
   contract_paths = discover_contracts(nodes_dir)

   # Parse on-demand during validation
   for path in contract_paths:
       if needs_validation(path):
           contract = parse_contract(path)
           validate_contract(contract)
   ```

2. **Contract Caching**: Cache parsed contracts between runs
   ```python
   contract_cache_path = ".onex_cache/contracts/"

   if contract_cache_exists(contract_path):
       contract = load_from_cache(contract_path)
   else:
       contract = parse_yaml(contract_path)
       save_to_cache(contract_path, contract)
   ```

3. **Parallel Parsing**: Parse multiple contracts concurrently
   ```python
   from concurrent.futures import ThreadPoolExecutor

   with ThreadPoolExecutor(max_workers=4) as executor:
       contracts = executor.map(parse_contract, contract_paths)
   ```

### 3. Pattern Validator

**Algorithm**: Linear file scan with AST analysis

**Time Complexity**: O(n) where n = number of Python files

**Performance Profile**:
```
File Discovery:    10-20ms  (os.walk)
AST Parsing:      30-150ms  (ast.parse per file)
Pattern Matching:  10-30ms  (regex and AST traversal)
Total:            50-200ms
```

**Optimization Strategies**:

1. **Compiled Regex**: Pre-compile regex patterns
   ```python
   # Compile once at module load
   MODEL_PREFIX_PATTERN = re.compile(r'^Model[A-Z]')
   ANTI_PATTERN = re.compile(r'(Manager|Handler|Helper)$')

   # Reuse throughout validation
   if MODEL_PREFIX_PATTERN.match(class_name):
       # ...
   ```

2. **Early Exit**: Skip non-Python files quickly
   ```python
   if not file.endswith('.py'):
       continue
   if file.startswith('__pycache__'):
       continue
   ```

3. **Selective Analysis**: Only analyze relevant AST nodes
   ```python
   for node in ast.walk(tree):
       if isinstance(node, ast.ClassDef):  # Only check class definitions
           validate_class_name(node.name)
   ```

### 4. Union Usage Validator

**Algorithm**: Linear type annotation parsing

**Time Complexity**: O(n) where n = number of Python files

**Performance Profile**:
```
File Discovery:    10-20ms  (os.walk)
AST Parsing:      30-150ms  (ast.parse per file)
Type Analysis:     10-30ms  (annotation node traversal)
Total:            50-200ms
```

**Optimization Strategies**:

1. **Type Annotation Filtering**: Skip files without type annotations
   ```python
   if not has_type_annotations(file_content):
       continue  # Skip files with no annotations
   ```

2. **Focused Traversal**: Only analyze type annotation nodes
   ```python
   for node in ast.walk(tree):
       if isinstance(node, (ast.FunctionDef, ast.AnnAssign)):
           if node.annotation:
               analyze_annotation(node.annotation)
   ```

3. **Union Count Threshold**: Stop early when threshold exceeded
   ```python
   union_count = 0
   for annotation in annotations:
       if is_union(annotation):
           union_count += 1
           if union_count > max_unions:
               return early_failure_result(union_count)
   ```

### 5. Circular Import Validator

**Algorithm**: Dependency graph analysis with cycle detection

**Time Complexity**: O(n²) where n = number of modules

**Performance Profile**:
```
File Discovery:     10-20ms   (os.walk)
Import Parsing:    50-200ms   (AST import extraction)
Graph Building:    50-300ms   (dependency graph construction)
Cycle Detection:  100-500ms   (depth-first search)
Total:           200-1000ms
```

**Optimization Strategies**:

1. **Incremental Graph Updates**: Only update graph for changed modules
   ```python
   graph = load_dependency_graph()

   for changed_file in changed_files:
       update_graph_node(graph, changed_file)

   # Only check cycles involving updated nodes
   check_cycles_from_nodes(graph, changed_nodes)
   ```

2. **Graph Caching**: Persist dependency graph between runs
   ```python
   graph_cache_path = ".onex_cache/import_graph.pkl"

   if graph_cache_exists():
       graph = load_graph_cache()
   else:
       graph = build_dependency_graph()
       save_graph_cache(graph)
   ```

3. **Early Cycle Detection**: Stop at first cycle found
   ```python
   def detect_cycles(graph, early_exit=True):
       for node in graph.nodes:
           if has_cycle_from(node):
               if early_exit:
                   return True  # Stop at first cycle
               cycles.append(node)
       return False
   ```

4. **Parallel Module Analysis**: Analyze modules concurrently
   ```python
   from concurrent.futures import ProcessPoolExecutor

   with ProcessPoolExecutor() as executor:
       import_maps = executor.map(extract_imports, modules)

   # Build graph from import maps
   graph = build_graph(import_maps)
   ```

## Validation Modes

### Quick Mode (--quick)

Skip MEDIUM priority validators for faster validation:

```bash
uv run python scripts/validate.py all --quick
```

**Performance**: ~250-600ms (50% faster)

**Skipped Validators**:
- Union usage
- Circular imports

**Use When**:
- Local development iteration
- Pre-commit hooks
- Rapid feedback loops

### Full Mode (default)

Run all validators:

```bash
uv run python scripts/validate.py all
```

**Performance**: ~450-1900ms

**Use When**:
- CI/CD pipelines
- Pre-release validation
- Comprehensive code quality checks

### Verbose Mode (--verbose)

Show detailed validation output:

```bash
uv run python scripts/validate.py all --verbose
```

**Performance**: +50-100ms overhead for detailed logging

**Use When**:
- Debugging validation issues
- Understanding validation failures
- Detailed reporting

## CI/CD Performance

### GitHub Actions Performance

Typical CI runtime breakdown:

```
Setup Python:           15-30s
Install uv:             5-10s
Load cached venv:        2-5s
Install dependencies:    0s (cached) or 60-120s (cold)
Install project:         5-10s
Run ONEX validators:     1-2s
Total:                  33-187s
```

**Optimization Strategies**:

1. **Dependency Caching**: Cache uv venv
   ```yaml
   - name: Load cached venv
     uses: actions/cache@v4
     with:
       path: .venv
       key: venv-${{ runner.os }}-${{ hashFiles('uv.lock') }}
   ```

2. **Parallel Jobs**: Run validators in parallel with other checks
   ```yaml
   jobs:
     lint:
       # ruff, black, isort, mypy
     test:
       # pytest
     onex-validation:
       # ONEX validators (runs in parallel)
   ```

3. **Quick Mode**: Use quick mode for PR checks
   ```yaml
   - name: Run ONEX validators (quick)
     run: uv run python scripts/validate.py all --quick
   ```

4. **Incremental Validation**: Validate only changed files
   ```bash
   # Get changed files from PR
   git diff --name-only origin/main...HEAD | grep '\.py$' > changed.txt

   # Validate only changed files
   uv run python scripts/validate.py --changed-files changed.txt
   ```

## Performance Monitoring

### Profiling Validators

Use Python profiling to identify bottlenecks:

```python
import cProfile
import pstats
from omnibase_infra.validation import validate_infra_all

profiler = cProfile.Profile()
profiler.enable()

results = validate_infra_all()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

### Benchmarking

Benchmark validation performance:

```python
import time
from omnibase_infra.validation import validate_infra_all

# Warm-up run
validate_infra_all()

# Benchmark
iterations = 10
start = time.time()

for _ in range(iterations):
    validate_infra_all()

elapsed = time.time() - start
avg_time = elapsed / iterations
print(f"Average validation time: {avg_time:.2f}s")
```

### Performance Regression Detection

Track validation performance over time:

```yaml
# .github/workflows/performance.yml
- name: Run performance benchmark
  run: |
    python scripts/benchmark_validation.py > perf_results.json

- name: Compare with baseline
  run: |
    python scripts/compare_perf.py perf_results.json baseline.json
```

## Scaling Considerations

### Large Codebases (>1000 files)

For large infrastructure codebases:

1. **Incremental Validation**: Only validate changed files
2. **Parallel Processing**: Use multiprocessing for validators
3. **Distributed Validation**: Split validation across multiple CI jobs
4. **Caching Strategy**: Aggressive caching of parsed AST/YAML

### Monorepo Considerations

For monorepo setups:

1. **Selective Validation**: Validate only affected packages
2. **Workspace Caching**: Share validation cache across workspaces
3. **Parallel Workspaces**: Validate workspaces in parallel

## Performance Targets

**Target Validation Times** (for omnibase_infra):

- **Local Development**: <500ms (quick mode)
- **CI/CD**: <2s (full mode)
- **Large Codebase**: <5s (with optimizations)

**Thresholds for Action**:

- **Warning**: >3s validation time
- **Optimization Required**: >5s validation time
- **Architecture Review**: >10s validation time

## Future Optimizations

Potential performance improvements:

1. **Incremental AST Parsing**: Cache AST trees between runs
2. **Watch Mode**: Continuous validation with file watching
3. **Rust Validators**: Rewrite critical validators in Rust
4. **Graph Database**: Use graph database for import analysis
5. **Distributed Validation**: Parallel validation across machines

## Conclusion

Current validation performance is acceptable for infrastructure codebase size. For larger codebases, implement incremental validation and caching strategies documented above.

**Key Takeaways**:
- Use quick mode for local development
- Enable caching in CI/CD
- Profile validators if performance degrades
- Consider incremental validation for large codebases

---

## Next Steps

- Validator Reference (internal knowledge base) - Detailed validator documentation
- Framework Integration (internal knowledge base) - Integration patterns
- Troubleshooting (internal knowledge base) - Performance troubleshooting
