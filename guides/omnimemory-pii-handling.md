---
type: guide
status: current
date: "2026-08-26"
title: "OmniMemory PII Handling"
topics:
  - omnimemory
  - pii
  - privacy
  - memory-storage
refs:
  - architecture/omnimemory-four-node-architecture.md
  - reference/omnimemory-handler-reuse-matrix.md
---

> **Last verified:** 2026-08-26 — migrated from the `omnimemory` repository. Triage verdict `MIGRATE_AS_IS`: every claim below was re-checked against live source and no drift was found. `PIIDetector`, `ModelPIIDetectorConfig` and `ModelPIIDetectionResult` are re-exported from `omnimemory.adapters` (confirmed in `adapters/__init__.py`); the `PIIType` members listed match `model_pii_type.py` exactly; the Not-Implemented status of `URL`, `PERSON_NAME` and `ADDRESS` is confirmed by the TODO markers in `adapter_pii_detector.py`; every `ModelPIIDetectorConfig` field named below exists in `model_pii_detector_config.py`. Only scrubbing was applied on migration: literal example addresses were replaced with placeholder forms, which does not change any behavioural claim.

# PII Handling Guide for Memory Systems

## Overview

OmniMemory includes a comprehensive PII (Personally Identifiable Information) detection system to ensure privacy compliance and data security in memory storage operations. This guide covers integration patterns, configuration options, and best practices for using the `PIIDetector` utility.

**Location**: `src/omnimemory/adapters/adapter_pii_detector.py`. `PIIDetector`,
`PIIType`, and the `Model*` PII result/match/config classes below are all
re-exported from `omnimemory.adapters` (backed by
`src/omnimemory/models/utils/model_pii_*.py`) — import from `omnimemory.adapters`,
not a submodule path.

---

## PII Types Detected

The `PIIType` enum defines all detectable PII categories:

| PII Type | Description | Pattern Examples | Confidence | Status |
|----------|-------------|------------------|------------|--------|
| `EMAIL` | Email addresses | `<user>@example.com` | 0.95 | Implemented |
| `PHONE` | Phone numbers (US/International) | `+1-555-123-4567`, `(555) 123-4567` | 0.75-0.90 | Implemented |
| `SSN` | Social Security Numbers | `123-45-6789`, `123456789` | 0.75-0.98 | Implemented |
| `CREDIT_CARD` | Credit card numbers (Visa, MC, Amex, Discover) | `4111111111111111` | 0.90 | Implemented |
| `IP_ADDRESS` | IPv4 and IPv6 addresses | `192.0.2.1`, `2001:0db8:...` | 0.90 | Implemented |
| `URL` | Web URLs | `https://example.com` | - | **Not Implemented** |
| `API_KEY` | API keys and tokens | `sk-...`, `ghp_...`, `AIza...`, `AWS...` | 0.90-0.98 | Implemented |
| `PASSWORD_HASH` | Password fields and hashes | `password=...` | 0.90 | Implemented |
| `PERSON_NAME` | Common person names | `John Smith` | - | **Not Implemented** |
| `ADDRESS` | Physical addresses | `123 Main St` | - | **Not Implemented** |

> **Note**: The following PII types are defined in the `PIIType` enum for future extensibility but do not yet have detection patterns implemented:
> - `URL` - Requires URL validation patterns
> - `PERSON_NAME` - Requires dictionary-based + NLP detection with expanded name database
> - `ADDRESS` - Requires geocoding or NLP integration for accurate detection

### API Key Detection

The detector includes specialized patterns for common API key formats:

| Provider | Pattern | Example |
|----------|---------|---------|
| OpenAI | `sk-[A-Za-z0-9]{32,}` | `sk-abc123...` |
| GitHub | `ghp_[A-Za-z0-9]{36}` | `ghp_abc123...` |
| Google | `AIza[A-Za-z0-9\-_]{35}` | `AIzaABC123...` |
| AWS | `AWS[A-Z0-9]{16,}` | `AWSACCESSKEY...` |
| Generic | `api_key=..., token=...` | Various formats |

---

## Core Components

### PIIDetector Class

```python
from omnimemory.adapters import PIIDetector, ModelPIIDetectorConfig

# Default configuration
detector = PIIDetector()

# Custom configuration
config = ModelPIIDetectorConfig(
    high_confidence=0.98,
    medium_confidence=0.90,
    low_confidence=0.60,
    max_text_length=50000,
    max_matches_per_type=50,
    enable_context_analysis=True
)
detector = PIIDetector(config=config)
```

### ModelPIIDetectionResult

The detection result provides comprehensive information:

```python
from pydantic import BaseModel, Field

class ModelPIIDetectionResult(BaseModel):
    """Result of PII detection scan."""
    has_pii: bool = Field(description="Whether any PII was detected")
    matches: List[ModelPIIMatch] = Field(default_factory=list, description="List of all PII matches found")
    sanitized_content: str = Field(description="Content with PII masked/removed")
    pii_types_detected: Set[PIIType] = Field(default_factory=set, description="Types of PII found")
    scan_duration_ms: float = Field(description="Scan performance metric")
```

### ModelPIIMatch

Each detected PII item includes:

```python
from pydantic import BaseModel, Field

class ModelPIIMatch(BaseModel):
    """A detected PII match in content."""
    pii_type: PIIType = Field(description="Type of PII (EMAIL, SSN, etc.)")
    value: str = Field(description="The detected PII value (may be masked)")
    start_index: int = Field(description="Start position in content")
    end_index: int = Field(description="End position in content")
    confidence: float = Field(description="Confidence score (0.0-1.0)")
    masked_value: str = Field(description="Masked version for sanitization")
```

---

## Sensitivity Levels

The `detect_pii()` method accepts a `sensitivity_level` parameter that adjusts detection thresholds:

| Level | Confidence Threshold | Use Case |
|-------|---------------------|----------|
| `"low"` | 0.95 (strict) | Production storage - only high-confidence matches |
| `"medium"` | 0.75 (balanced) | General use - balanced precision/recall |
| `"high"` | 0.60 (permissive) | Security audits - catch potential PII |

```python
# Low sensitivity - only high-confidence matches (production storage)
result = detector.detect_pii(content, sensitivity_level="low")

# Medium sensitivity - balanced detection (default)
result = detector.detect_pii(content, sensitivity_level="medium")

# High sensitivity - aggressive detection (security audits)
result = detector.detect_pii(content, sensitivity_level="high")
```

---

## Integration Guide

### Basic Usage

```python
from omnimemory.adapters import PIIDetector, PIIType

detector = PIIDetector()

# Detect PII in content
content = "Contact <user>@example.com or call 555-123-4567"
result = detector.detect_pii(content)

if result.has_pii:
    print(f"Found {len(result.matches)} PII items")
    print(f"Types: {result.pii_types_detected}")
    print(f"Sanitized: {result.sanitized_content}")
    # Output: Contact ***@***.*** or call ***-***-****
```

### Memory Storage Integration

**Pattern 1: Pre-Storage Validation**

```python
from omnimemory.adapters import PIIDetector

class MemoryStorageNode:
    def __init__(self):
        self.pii_detector = PIIDetector()

    async def store_memory(
        self,
        content: str,
        metadata: dict,
        allow_pii: bool = False
    ) -> MemoryStorageResult:
        """Store memory with PII validation."""

        # Detect PII before storage
        pii_result = self.pii_detector.detect_pii(
            content,
            sensitivity_level="medium"
        )

        if pii_result.has_pii and not allow_pii:
            # Option 1: Reject storage
            raise PIIDetectedError(
                f"Content contains PII: {pii_result.pii_types_detected}"
            )

            # Option 2: Store sanitized version
            # content = pii_result.sanitized_content

        # Proceed with storage
        return await self._persist_memory(content, metadata)
```

**Pattern 2: Automatic Sanitization**

```python
class SecureMemoryStorage:
    def __init__(self, auto_sanitize: bool = True):
        self.pii_detector = PIIDetector()
        self.auto_sanitize = auto_sanitize

    async def store(self, content: str) -> StorageResult:
        """Store with automatic PII sanitization."""

        result = self.pii_detector.detect_pii(content)

        # Log detected PII types (without values)
        if result.has_pii:
            logger.warning(
                "PII detected and sanitized",
                pii_types=list(result.pii_types_detected),
                match_count=len(result.matches),
                scan_duration_ms=result.scan_duration_ms
            )

        # Store sanitized content
        stored_content = (
            result.sanitized_content if self.auto_sanitize
            else content
        )

        return await self._persist(stored_content)
```

**Pattern 3: Safety Check Before Storage**

```python
class MemoryValidator:
    def __init__(self):
        self.pii_detector = PIIDetector()

    def validate_for_storage(
        self,
        content: str,
        max_allowed_pii: int = 0
    ) -> ValidationResult:
        """Validate content is safe for storage."""

        is_safe = self.pii_detector.is_content_safe(
            content,
            max_pii_count=max_allowed_pii
        )

        if not is_safe:
            # Get details for error message
            result = self.pii_detector.detect_pii(content, "high")
            return ValidationResult(
                valid=False,
                reason=f"Contains {len(result.matches)} PII items",
                pii_types=result.pii_types_detected
            )

        return ValidationResult(valid=True)
```

### Vector Memory Integration

```python
from omnimemory.adapters import PIIDetector

class VectorMemoryNode:
    def __init__(self):
        self.pii_detector = PIIDetector()

    async def store_embedding(
        self,
        text: str,
        embedding: List[float],
        metadata: dict
    ) -> str:
        """Store vector embedding with PII-free text."""

        # Sanitize text before storing with embedding
        pii_result = self.pii_detector.detect_pii(text)

        # Store sanitized text with embedding
        record = VectorRecord(
            text=pii_result.sanitized_content,
            embedding=embedding,
            metadata={
                **metadata,
                "pii_detected": pii_result.has_pii,
                "pii_types": [t.value for t in pii_result.pii_types_detected],
            }
        )

        return await self.vector_store.upsert(record)
```

### Batch Processing

```python
from typing import List, Tuple
from omnimemory.adapters import PIIDetector, ModelPIIDetectionResult

class BatchMemoryProcessor:
    def __init__(self):
        self.pii_detector = PIIDetector()

    def process_batch(
        self,
        items: List[str]
    ) -> Tuple[List[str], List[ModelPIIDetectionResult]]:
        """Process batch of items with PII detection."""

        sanitized_items = []
        detection_results = []

        for item in items:
            result = self.pii_detector.detect_pii(item)
            sanitized_items.append(result.sanitized_content)
            detection_results.append(result)

        return sanitized_items, detection_results

    def get_batch_statistics(
        self,
        results: List[ModelPIIDetectionResult]
    ) -> dict:
        """Compute statistics for batch processing."""

        total_pii_items = sum(r.has_pii for r in results)
        all_pii_types = set()
        total_matches = 0

        for result in results:
            all_pii_types.update(result.pii_types_detected)
            total_matches += len(result.matches)

        return {
            "total_items": len(results),
            "items_with_pii": total_pii_items,
            "pii_percentage": (total_pii_items / len(results) * 100) if results else 0,
            "total_matches": total_matches,
            "pii_types_found": [t.value for t in all_pii_types],
        }
```

---

## Configuration Options

### ModelPIIDetectorConfig

```python
from omnimemory.adapters import ModelPIIDetectorConfig

config = ModelPIIDetectorConfig(
    # Confidence thresholds
    high_confidence=0.98,           # For definite patterns (SSN with dashes)
    medium_high_confidence=0.95,    # For strong patterns (emails)
    medium_confidence=0.90,         # For common patterns (credit cards)
    reduced_confidence=0.75,        # For looser patterns (phone numbers)
    low_confidence=0.60,            # For weak patterns (names)

    # Pattern matching limits
    max_text_length=50000,          # Maximum content length to scan
    max_matches_per_type=100,       # Limit matches per PII type

    # Context analysis
    enable_context_analysis=True,   # Enable context-aware detection
    context_window_size=50,         # Characters around match to analyze
)
```

### Configuration Presets

```python
# Production preset - strict detection, performance optimized
PRODUCTION_CONFIG = ModelPIIDetectorConfig(
    high_confidence=0.98,
    medium_confidence=0.92,
    low_confidence=0.80,
    max_text_length=50000,
    max_matches_per_type=50,
)

# Development preset - balanced detection
DEVELOPMENT_CONFIG = ModelPIIDetectorConfig(
    high_confidence=0.95,
    medium_confidence=0.85,
    low_confidence=0.70,
    max_text_length=50000,
    max_matches_per_type=100,
)

# Audit preset - aggressive detection
AUDIT_CONFIG = ModelPIIDetectorConfig(
    high_confidence=0.90,
    medium_confidence=0.75,
    low_confidence=0.50,
    max_text_length=200000,
    max_matches_per_type=500,
    enable_context_analysis=True,
)
```

---

## Best Practices

### 1. Always Scan Before Storage

```python
# CORRECT: Scan before any persistence operation
async def store_memory(self, content: str) -> str:
    result = self.pii_detector.detect_pii(content)
    if result.has_pii:
        content = result.sanitized_content
    return await self._persist(content)

# INCORRECT: Storing without PII check
async def store_memory(self, content: str) -> str:
    return await self._persist(content)  # PII may leak
```

### 2. Log Detection Events (Not Values)

```python
# CORRECT: Log PII types and counts, not actual values
if result.has_pii:
    logger.warning(
        "PII detected",
        types=[t.value for t in result.pii_types_detected],
        count=len(result.matches)
    )

# INCORRECT: Logging actual PII values
if result.has_pii:
    logger.warning(f"Found PII: {result.matches}")  # Leaks PII to logs
```

### 3. Use Appropriate Sensitivity Levels

```python
# User-facing storage: low sensitivity (strict)
user_result = detector.detect_pii(user_input, sensitivity_level="low")

# Internal analytics: medium sensitivity (balanced)
analytics_result = detector.detect_pii(analytics_data, sensitivity_level="medium")

# Security audit: high sensitivity (permissive)
audit_result = detector.detect_pii(audit_data, sensitivity_level="high")
```

### 4. Handle Detection Errors Gracefully

```python
async def safe_detect_pii(self, content: str) -> ModelPIIDetectionResult:
    """Detect PII with graceful error handling."""
    try:
        return self.pii_detector.detect_pii(content)
    except ValueError as e:
        # Content too long - truncate and retry
        if "exceeds maximum" in str(e):
            truncated = content[:self.pii_detector.config.max_text_length]
            return self.pii_detector.detect_pii(truncated)
        raise
    except Exception as e:
        logger.error("PII detection failed", error=str(e))
        # Fail safe: assume PII present
        return ModelPIIDetectionResult(
            has_pii=True,
            matches=[],
            sanitized_content="[CONTENT_REDACTED_DUE_TO_ERROR]",
            pii_types_detected=set(),
            scan_duration_ms=0.0
        )
```

### 5. Validate Metadata Too

```python
def validate_memory_record(self, content: str, metadata: dict) -> bool:
    """Validate both content and metadata for PII."""

    # Check content
    content_result = self.pii_detector.detect_pii(content)

    # Check metadata values
    metadata_str = json.dumps(metadata)
    metadata_result = self.pii_detector.detect_pii(metadata_str)

    return not (content_result.has_pii or metadata_result.has_pii)
```

### 6. Monitor Detection Performance

```python
import time
from dataclasses import dataclass

@dataclass
class PIIMetrics:
    total_scans: int = 0
    total_pii_detected: int = 0
    average_scan_ms: float = 0.0

class MonitoredPIIDetector:
    def __init__(self):
        self.detector = PIIDetector()
        self.metrics = PIIMetrics()

    def detect_pii(self, content: str, sensitivity_level: str = "medium"):
        result = self.detector.detect_pii(content, sensitivity_level)

        # Update metrics
        self.metrics.total_scans += 1
        if result.has_pii:
            self.metrics.total_pii_detected += len(result.matches)

        # Rolling average
        self.metrics.average_scan_ms = (
            (self.metrics.average_scan_ms * (self.metrics.total_scans - 1) +
             result.scan_duration_ms) / self.metrics.total_scans
        )

        return result
```

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `ValueError: Content length exceeds maximum` | Content too long | Truncate content or increase `max_text_length` |
| Regex timeout | Complex patterns on large text | Reduce content size or simplify patterns |
| Memory errors | Too many matches | Reduce `max_matches_per_type` |

### Custom Exception Classes

```python
class PIIError(Exception):
    """Base exception for PII-related errors."""
    pass

class PIIDetectedError(PIIError):
    """Raised when PII is detected and storage is blocked."""
    def __init__(self, pii_types: Set[PIIType], match_count: int):
        self.pii_types = pii_types
        self.match_count = match_count
        super().__init__(
            f"Content contains {match_count} PII items of types: {pii_types}"
        )

class PIISanitizationError(PIIError):
    """Raised when PII sanitization fails."""
    pass
```

---

## Testing

### Unit Test Examples

```python
import pytest
from omnimemory.adapters import PIIDetector, PIIType

class TestPIIDetector:
    def setup_method(self):
        self.detector = PIIDetector()

    def test_detects_email(self):
        result = self.detector.detect_pii("Contact: <user>@example.com")
        assert result.has_pii
        assert PIIType.EMAIL in result.pii_types_detected

    def test_detects_ssn(self):
        result = self.detector.detect_pii("SSN: 123-45-6789")
        assert result.has_pii
        assert PIIType.SSN in result.pii_types_detected

    def test_sanitizes_content(self):
        result = self.detector.detect_pii("Email: <user>@example.com")
        assert "<user>@example.com" not in result.sanitized_content
        assert "***@***" in result.sanitized_content

    def test_no_pii_returns_safe(self):
        result = self.detector.detect_pii("Hello, world!")
        assert not result.has_pii
        assert len(result.matches) == 0

    def test_is_content_safe(self):
        assert self.detector.is_content_safe("Hello, world!")
        assert not self.detector.is_content_safe("Email: <user>@example.com")

    def test_detects_api_keys(self):
        # OpenAI key pattern
        result = self.detector.detect_pii("key: sk-abcdefghijklmnopqrstuvwxyz123456")
        assert result.has_pii
        assert PIIType.API_KEY in result.pii_types_detected

        # GitHub token pattern
        result = self.detector.detect_pii("token: ghp_abcdefghijklmnopqrstuvwxyz1234567890")
        assert result.has_pii
```

---

## Performance Considerations

PII detection is a critical component of memory operations and must meet OmniMemory's performance requirements. This section documents performance targets, benchmarks, and optimization strategies.

### Performance Targets

The PIIDetector is designed to meet OmniMemory's overall performance specifications from [architecture requirements](../architecture/omnimemory-four-node-architecture.md):

| Metric | Target | Context |
|--------|--------|---------|
| **Memory Operations** | <100ms (95th percentile) | Overall system target for all memory operations |
| **PII Scan (50KB text)** | <100ms | Maximum text length with PII present |
| **PII Scan (clean text)** | <50ms | When no PII patterns are found |
| **PII Throughput** | 10+ scans/second | For 10KB documents at medium sensitivity |
| **Stress Test (max length)** | <200ms | Maximum text length with high sensitivity |

These targets ensure PII detection does not become a bottleneck in memory storage workflows.

### Performance Benchmarks

Automated performance tests are available in `tests/test_performance.py`. The `TestPIIDetectorPerformance` class provides benchmarks for:

```bash
# Run all PII performance benchmarks
pytest tests/test_performance.py -v -k "TestPIIDetectorPerformance"

# Run quick benchmarks only (skip slow throughput tests)
pytest tests/test_performance.py -v -m "benchmark and not slow"
```

**Key benchmark tests:**
- `test_pii_scan_50kb_under_100ms` - Core performance validation
- `test_pii_scan_clean_text_performance` - Clean text optimization
- `test_pii_scan_throughput` - Sustained throughput measurement
- `test_pii_scan_reports_duration` - Duration tracking validation

### Optimization Strategies

#### 1. Choose Appropriate Sensitivity Level

Sensitivity level significantly impacts performance due to pattern matching thresholds:

| Sensitivity | Patterns Evaluated | Performance Impact | Use Case |
|-------------|-------------------|-------------------|----------|
| `"low"` | Fewest (high-confidence only) | Fastest | Production storage, high-throughput |
| `"medium"` | Balanced | Moderate | General use, default setting |
| `"high"` | Most (includes weak patterns) | Slowest | Security audits, batch processing |

```python
# High-throughput scenario: use low sensitivity
result = detector.detect_pii(content, sensitivity_level="low")

# Security audit: use high sensitivity (accept performance cost)
result = detector.detect_pii(content, sensitivity_level="high")
```

#### 2. Configure max_text_length Appropriately

The `max_text_length` setting controls memory usage and scan time:

```python
# Production preset - optimized for performance
config = ModelPIIDetectorConfig(
    max_text_length=50000,      # 50KB limit
    max_matches_per_type=50,    # Limit match processing
)

# Large document processing - accept higher memory/time
config = ModelPIIDetectorConfig(
    max_text_length=200000,     # 200KB limit
    max_matches_per_type=500,   # More matches allowed
)
```

**Memory usage considerations:**
- Each additional 10KB of text adds approximately 1-2ms scan time
- Match deduplication and sanitization have O(n log n) complexity
- `max_matches_per_type` limits memory for documents with many PII items

#### 3. Pre-filter Content When Possible

For known content types, skip unnecessary scans:

```python
class OptimizedMemoryStorage:
    def __init__(self):
        self.pii_detector = PIIDetector()

    async def store(self, content: str, content_type: str) -> StorageResult:
        # Skip PII scan for known-safe content types
        if content_type in ("metrics", "logs_sanitized", "system_generated"):
            return await self._persist(content)

        # Scan user-generated content
        result = self.pii_detector.detect_pii(content, sensitivity_level="medium")
        return await self._persist(result.sanitized_content)
```

#### 4. Batch Processing Optimization

For bulk operations, process in parallel while respecting throughput limits:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class BatchPIIProcessor:
    def __init__(self, max_workers: int = 4):
        self.detector = PIIDetector()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def process_batch(self, items: List[str]) -> List[ModelPIIDetectionResult]:
        """Process batch with controlled parallelism."""
        loop = asyncio.get_event_loop()

        # Process in parallel using thread pool
        futures = [
            loop.run_in_executor(
                self.executor,
                self.detector.detect_pii,
                item,
                "medium"
            )
            for item in items
        ]

        return await asyncio.gather(*futures)
```

#### 5. Monitor and Track Performance

Use the built-in `scan_duration_ms` metric for observability:

```python
class PerformanceTrackedDetector:
    def __init__(self, alert_threshold_ms: float = 100.0):
        self.detector = PIIDetector()
        self.alert_threshold_ms = alert_threshold_ms
        self.slow_scans = 0

    def detect_pii(self, content: str, sensitivity_level: str = "medium"):
        result = self.detector.detect_pii(content, sensitivity_level)

        if result.scan_duration_ms > self.alert_threshold_ms:
            self.slow_scans += 1
            logger.warning(
                "PII scan exceeded threshold",
                duration_ms=result.scan_duration_ms,
                content_length=len(content),
                sensitivity=sensitivity_level,
                matches_found=len(result.matches)
            )

        return result
```

### Performance vs. Security Trade-offs

| Scenario | Recommended Configuration | Rationale |
|----------|--------------------------|-----------|
| Real-time API responses | Low sensitivity, 10KB limit | User-facing latency requirements |
| Background batch jobs | High sensitivity, 200KB limit | Thoroughness over speed |
| Stream processing | Medium sensitivity, 50KB limit | Balanced approach |
| Security audits | High sensitivity, no limits | Maximum detection, scheduled runs |

### Troubleshooting Performance Issues

**Symptom: Scans consistently exceed 100ms**
- Check content length (reduce `max_text_length` if needed)
- Lower sensitivity level for high-throughput paths
- Profile regex patterns for complex content

**Symptom: High memory usage during batch processing**
- Reduce `max_matches_per_type` setting
- Process in smaller batches
- Implement streaming for very large documents

**Symptom: Inconsistent scan times**
- Content with many PII items takes longer to sanitize
- High-sensitivity scans evaluate more patterns
- Consider caching for repeated content

---

## Related Documentation

- [OmniMemory Handler Reuse Matrix](../reference/omnimemory-handler-reuse-matrix.md) — handler integration patterns
- [OmniMemory Four-Node Architecture](../architecture/omnimemory-four-node-architecture.md) — the node archetypes the storage path runs on
- Node implementations live in the `omnimemory` repository under `src/omnimemory/nodes/`

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-01-18 | Initial documentation |
