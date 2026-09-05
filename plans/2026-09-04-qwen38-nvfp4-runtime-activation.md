---
type: plan
status: draft
date: "2026-09-04"
title: "Qwen3.8 NVFP4 immutable runtime activation and disposable canary"
topics: [runtime, model-serving, nvfp4, reproducibility, attestation, rsd]
refs: ["architecture/onex-runtime-overview.md", "doctrine/runtime-complexity-isolated.md"]
---

# Qwen3.8 NVFP4 immutable runtime activation and disposable canary

## Purpose

Define a fail-closed activation path for a Qwen3.8-27B NVFP4 runtime on a
Linux x86_64 Blackwell GPU. The plan separates published artifact identity
from evidence required to authorize execution. The packaged RSD overlay remains
`execute_enabled: false`; activation is not executable until a separately
recorded startup attestation passes.

This is an implementation plan, not evidence that a runtime has been started.
No endpoint, credential, host, port, or local filesystem location is part of
the public contract.

## Non-goals

- Starting, restarting, or modifying any service.
- Resolving model names through a network or environment fallback at runtime.
- Publishing a new container image before its license obligations are cleared.
- Treating a model-card benchmark, constructible DTO, or valid signature alone
  as execution authority.
- Persisting endpoint values, credentials, topology, or secret material.

## Immutable candidate manifest

The candidate uses the exact public model revision below. Every consumer must
verify the revision and all listed large-file hashes before accepting it.

### Model

```yaml
repository: gittensor-model-hub/Qwen3.8-27B-NVFP4-RTX5090
revision: 0cc27958cefbbe231782ec8511de8c4eb5233348
license: Apache-2.0
base_model: Qwen/Qwen3.8-27B
quantization: NVIDIA ModelOpt NVFP4 W4A4, group_size=16
kv_cache: FP8
modelopt_source_commit: c4129b6e03d3c564e04359e6d0c6057c9a59183f
total_size_bytes: 18765214312
shards:
  - path: model-00001-of-00003.safetensors
    size_bytes: 9972777720
    sha256: cdd37b0e61eccc8a3d7d08f9d1a4f52856a9d88e4e8b42089bd18a970e3a01ec
  - path: model-00002-of-00003.safetensors
    size_bytes: 8048202912
    sha256: 4b547449a2b23c6cd414da0cf65ff9d7e17ad9aa2b119beedcbba14f649eb1dd
  - path: model-00003-of-00003.safetensors
    size_bytes: 744532384
    sha256: 9ce944d534eabdd493076a3a52c7ebd31f41c135b340a1ea95c5a695e6f1f6b2
metadata_sha256:
  config.json: 78f65e03f2ac08a39320bf4a2633f1ae1526144da0fba1904b7371e682c304ea
  hf_quant_config.json: 2c30a0d7e08c5eede4a273c9862aa90f49adfda1cd661dd564742749de9c1a2b
  model.safetensors.index.json: 4f0c8847dd549636c873737a4703ff1f215a98ec6d5e90b082b31e9e26f4e765
  tokenizer.json: 0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3
```

The candidate artifact receipt also carries an aggregate checkpoint beginning
`e46ef4`. Its complete digest is not reproduced here without the signed
receipt: deriving a new aggregate over 18.7 GB would require an artifact pull,
which is outside this documentation-only plan. Activation must verify the
complete receipt value in the private approval record in addition to every
publicly listed shard and metadata hash; the prefix is never an authority.

The checkpoint intentionally leaves its vision tower, embeddings, MTP
components, and selected recurrent-attention support modules in BF16. W4A4
must therefore be attested for the intended linear/GEMM path, not inferred
from the repository label.

### Runtime

The preferred reproducibility boundary is the published amd64 image, pinned
by manifest digest rather than tag:

```yaml
image: vllm/vllm-openai
image_index_sha256: 0a51ea5b4ae2dc5d81890e5173f54203d2a3ae0cfffe51b8fd2afd4391bfd967
amd64_manifest_sha256: c2f3b1b964e47809b722b5e75b61b1e7b39a50f70388cf2bf2418f16a9f31da2
image_config_sha256: e0cfcfcb9b86e2c2d0d52a93689773f20f380cb8e050a24ce550c44f6f55c5eb
vllm_version: 0.27.1
vllm_source_commit: 6e448d0ea9bf3d88d898b65449ca6dc2aec170ac
cuda_version: 13.0.2
python_version: "3.12"
nccl_version: 2.30.7
flashinfer_version: 0.6.16.post3
compute_capability: sm_120
```

The corresponding official package metadata is retained for independent
verification or a future hermetic build:

```yaml
vllm_x86_64_wheel_sha256: 98e9fc2a1ed8549a733c9d1b242e2002b82367da9e29e37801761438cb3a2670
vllm_source_sdist_sha256: eec2d54d137ac1e59cb4c39226dfee1943eefc8f4788f5821d7300d6acbdb646
torch_2.13.0_cu130_cp312_sha256: 8db7338e6895c3d4bd89a02ff4209507d1f0cf2ffeb3b898538b5a07d1ea8c1e
torchvision_0.28.0_cu130_cp312_sha256: 8a0008d34ccc4e81066b97ff0ae5a34c676bfdf3464baf40c01b320dc9a45ce0
torchaudio_2.11.0_cu130_cp312_sha256: 3fba988f4301fe13547fe5e99c76d9ae36a27e19ded82eeffed9d2456e12edef
flashinfer_python_sha256: caf686b9b079abe1c9d65ab505698bd325e8072de40afd822f2c74f2ac3bc601
flashinfer_cubin_sha256: c79fba990aee2a7c7ef64208bb65900e45fe23c3a223f3dfc21eef225f43cba2
flashinfer_jit_cache_cu130_x86_64_sha256: abcca93faa2fbbc9a98394ccc44ab657627b91e49da2624efd26a6ff669264ab
```

The official image is built with CUDA 13.0.2. `RuntimeActivationOverlayV1`
is image-only: it accepts only this immutable OCI index, its Linux amd64
manifest, and its image config digest. It rejects source-build and
wheel-only modes, mutable tags or aliases, architecture substitution, and
any dependency set that is not represented by the signed image identity.
The package hashes above remain provenance for independent audit; they are
not an alternate execution boundary.

The pinned [vLLM model source](https://raw.githubusercontent.com/vllm-project/vllm/v0.27.1/vllm/model_executor/models/qwen3_5.py)
defines the exact `Qwen3_5ForConditionalGeneration` architecture, and the
pinned [vLLM registry](https://raw.githubusercontent.com/vllm-project/vllm/v0.27.1/vllm/model_executor/models/registry.py)
and [supported-models table](https://raw.githubusercontent.com/vllm-project/vllm/v0.27.1/docs/models/supported_models.md)
list it as built in. The model revision's
[`config.json`](https://huggingface.co/gittensor-model-hub/Qwen3.8-27B-NVFP4-RTX5090/blob/0cc27958cefbbe231782ec8511de8c4eb5233348/config.json)
declares that same architecture and `model_type: qwen3_5`. This is the
primary-source basis for signing `trust_remote_code: false`; startup still
has to prove the loaded architecture and all other facts below. A future
checkpoint with a different architecture must fail closed rather than
re-enable remote code.

## Versioned signed activation overlay

Add a contract-owned `RuntimeActivationOverlayV1` with exactly one accepted
wire encoding: canonical UTF-8 JSON (sorted object keys, no insignificant
whitespace, no duplicate keys, no aliases, and no alternate YAML form) and a
detached Ed25519 signature. The verifier rejects unknown fields,
non-canonical encoding, missing hashes, expired approvals, mismatched
signatures, and values outside declared enums or bounds. The public overlay
carries logical opaque references only. Its required field shape is:

```json
{"activation_id":"<opaque-activation-id>","approval":{"expires_at":"<utc-instant>","issued_at":"<utc-instant>","signer_fingerprint":"<activation-signer-fingerprint>"},"dependencies":{"cuda":"<version>","flashinfer_cubin":"<version-and-sha256>","flashinfer_jit_cache":"<version-and-sha256>","flashinfer_python":"<version-and-sha256>","nccl":"<version>","python":"<version>","torch":"<version-and-build>","vllm_source_commit":"<commit>","vllm_version":"<version>"},"execution_enabled":false,"external_served_model_id":"Qwen/Qwen3.8-27B","hardware":{"compute_capability":"sm_120","device_class":"rtx-5090","device_identity_sha256":"<immutable-gpu-identity-digest>","exclusive_allocation":true,"gpu_memory_bytes":34359738368,"process_exclusivity_evidence_sha256":"<process-evidence-digest>","compute_mode_evidence_sha256":"<compute-mode-evidence-digest>","selected_device_count":1},"image":{"amd64_manifest_sha256":"<image-manifest-sha256>","config_sha256":"<image-config-sha256>","index_sha256":"<image-index-sha256>","repository":"vllm/vllm-openai"},"launch_profile_served_model_id":"qwen38-nvfp4-rtx5090-v1","launch_profile_sha256":"40defad1345d27226916e8946647482bb3eaaeca96c4330968e6a0bcaad074b3","model":{"config_sha256":"<config-sha256>","manifest_sha256":"<complete-snapshot-manifest-sha256>","quant_config_sha256":"<quant-config-sha256>","repository":"<model-repository>","revision":"<model-revision>","shard_sha256":["<shard-1>","<shard-2>","<shard-3>"]},"schema":"RuntimeActivationOverlayV1","startup_attestation":{"required":true,"sha256":"<attestation-digest>"},"target_ref":"<opaque-target-ref>","credential_ref":"<opaque-credential-ref>"}
```

`gpu_memory_bytes` is an unsigned integer measured from the immutable device
identity; the example's value is illustrative and is not an authorization
for a different device.

`model.manifest_sha256` is a signed digest of a complete, revision-scoped
snapshot manifest. That manifest lists every accepted model path, byte size,
and SHA-256—including config, quantization config, index, tokenizer,
generation metadata, license/notice files, and all weight shards—and rejects
missing, mutated, added, or unlisted files. Since the image has built-in
Qwen3.5 support, executable model Python is not accepted and
`trust_remote_code: false` is mandatory; the manifest remains required for
complete model identity. Resolution is revision-scoped and offline after the
verified immutable pull; cache fallback, network resolution, and unlisted
files are not permitted.

The production overlay remains disabled until the verifier confirms the
attestation digest. Activation and route-target authority signatures use
distinct trust anchors; a valid activation signer cannot redirect an opaque
target or credential reference. No resolver, environment fallback, network
probe, endpoint value, or credential value is accepted by this contract.

The two model identities are deliberately distinct and both are signed launch
inputs. `external_served_model_id` is the OpenAI-facing identity and is exactly
`Qwen/Qwen3.8-27B`; `launch_profile_served_model_id` is the internal launch
identity and is exactly `qwen38-nvfp4-rtx5090-v1`. They are neither aliases nor
interchangeable. Matching is byte-for-byte and case-sensitive: no spelling,
case, namespace, normalization, or fallback alias is accepted. The verified
OpenAI model listing contains the external ID exactly once; the startup
attestation and launch-profile digest bind both IDs.

The canonical launch profile for the candidate is:

```json
{"external_served_model_id":"Qwen/Qwen3.8-27B","gpu_memory_utilization":0.97,"kv_cache_dtype":"fp8","launch_profile_served_model_id":"qwen38-nvfp4-rtx5090-v1","max_model_len":262144,"max_num_seqs":16,"model":"gittensor-model-hub/Qwen3.8-27B-NVFP4-RTX5090@0cc27958cefbbe231782ec8511de8c4eb5233348","quantization":"modelopt","reasoning_parser":"qwen3","tensor_parallel_size":1,"tool_call_parser":"qwen3_xml","trust_remote_code":false}
```

Its UTF-8 canonical-byte SHA-256 is
`40defad1345d27226916e8946647482bb3eaaeca96c4330968e6a0bcaad074b3`.

## Signed startup attestation

`RuntimeStartupAttestationV1` is a canonical UTF-8 JSON record with a
detached Ed25519 signature under a trust anchor distinct from both the
activation signer and the route-target authority. Its signed fields include
exactly: `schema_version`, `attestation_id`, `overlay_sha256`,
`activation_id`, `approval_signer_fingerprint`, `approval_issued_at`,
`approval_expires_at`, `attested_at`, `route_authority_sha256`,
`target_configuration_sha256`, `credential_reference_sha256`,
`snapshot_manifest_sha256`, `image_index_sha256`, `amd64_manifest_sha256`,
`image_config_sha256`, `launch_profile_sha256`, `external_served_model_id`,
`launch_profile_served_model_id`, `hardware_identity_sha256`,
`startup_record_sha256`, and
`signer_fingerprint`. Route, target, and credential values never appear;
their opaque authority digests are the commitments.

The verifier requires an injected UTC clock and a short maximum attestation
lifetime (no more than five minutes). It checks canonical bytes, the distinct
attestation trust anchor, signature, replay-unique `attestation_id`, exact
overlay/activation/approval interval and route/target/credential digest
equality, and `approval_issued_at <= attested_at <= approval_expires_at` with
the attestation not in the future. It rejects cross-overlay, cross-reference,
cross-activation, expired, stale, boundary-overrun, duplicate, unknown, or
replayed records before any process starts. Missing startup evidence,
fallback evidence, or an unavailable verifier is fail-closed.

## Disposable canary lifecycle

The canary is a separately approved execution gate. General authorization to
modify a development runtime does not authorize interrupting an existing
service, allocating its GPU, or changing its traffic path.

1. **Identity and baseline.** Prove immutable GPU identity, device class
   `rtx-5090`, `sm_120`, exact memory bytes, and `selected_device_count: 1`
   from approved read-only evidence. Prove exclusive allocation with
   process-exclusivity and compute-mode evidence digests; reject shared,
   ambiguous, or mutable device claims. Record a rollback pointer and a
   baseline health/result digest. Abort if the resource is not explicitly
   quiescent.
2. **Prepare.** Verify the image index, amd64 manifest, image config, model
   revision, metadata, every shard hash, and every dependency identity before
   starting anything. Reject tags, mutable aliases, missing files, and an
   unexpected architecture.
3. **Isolate.** Use a disposable service identity and an opaque target
   reference. Do not reuse the existing service identity, credentials, route,
   state directory, or durable data.
4. **Start and attest.** Start only with the canonical launch-profile hash
   and `trust_remote_code: false`. Capture a bounded, redacted startup record
   proving the exact immutable GPU identity/class/SM/memory, one selected
   device, exclusive process allocation and compute mode, ModelOpt NVFP4 W4A4,
   FP8 KV, native `lm_head` quantization, and actual
   `FlashInferCutlassNvFp4LinearKernel` selection. Any fallback, mismatch,
   multiple-device claim, missing line, JIT failure, or uncertain state is a
   failed attestation.
5. **Exercise narrowly.** Run a bounded deterministic inference smoke and a
   bounded RSD adapter smoke using opaque references. Record request/result
   digests and resource ceilings; do not expose endpoint or credential values.
6. **Rollback.** Stop the disposable identity, verify no process/resource
   remains, restore the retained rollback state, and re-check baseline health.
   Rollback is mandatory on attestation failure, timeout, unexpected output,
   or any service interruption.
7. **Cleanup proof.** Record cleanup and restoration digests. The activation
   remains disabled unless all required evidence is complete and independently
   verified.

## Attestation acceptance criteria

The startup attestation must bind, in one signed canonical record,
the image index/manifest/config digests, model revision and shard hashes,
dependency identities, launch-profile hash, both exact model identities,
hardware capability, approval interval, and startup-log digest. It must show:

- external served-model ID exactly `Qwen/Qwen3.8-27B` and launch-profile
  served-model ID exactly `qwen38-nvfp4-rtx5090-v1`, each bound to the overlay
  and launch-profile digest with no alias or case-normalized alternative;

- `modelopt` quantization with NVFP4 W4A4 group size 16;
- FP8 KV cache;
- immutable GPU identity and class, `sm_120`, exact memory bytes, exactly one
  selected device, and exclusive process/compute-mode evidence;
- native FlashInfer CUTLASS FP4 GEMM selection, with no conversion or fallback;
- native NVFP4 `lm_head` loading for this revision;
- successful bounded inference and adapter checks;
- no leaked process, state, or disposable identity after completion.

The model card's throughput and startup narrative is useful provenance but is
not this attestation. Published benchmark conditions and results must remain
labelled as benchmark claims, not current deployment evidence.

## Licensing and public-release gate

The model, its declared Qwen base, vLLM, and FlashInfer metadata identify
Apache-2.0 licensing. Preserve the model LICENSE and required attribution in
any artifact bundle. The NVIDIA CUDA/NCCL base and the published vLLM image
carry additional NVIDIA container/license terms; review those terms before
redistributing an image or repackaging its layers. No public image
redistribution is approved until that review is complete.

## Acceptance tests

- Canonical overlay round-trip is byte-stable and signature verification is
  deterministic.
- Any changed image, model, shard, dependency, launch field, external served
  model ID, launch-profile served model ID, hardware capability, approval
  interval, or attestation digest is rejected; a substituted alias or case
  variant of either ID is rejected.
- `execute_enabled: true` is rejected without a valid startup attestation and
  distinct activation/route trust anchors.
- Unknown fields, mutable tags, architecture mismatches, expired approvals,
  fallback-kernel evidence, and missing cleanup proof fail closed.
- A source-build or wheel-only overlay, `trust_remote_code: true`, incomplete
  snapshot manifest, added/unlisted model file, multiple selected devices,
  mutable GPU identity, or non-exclusive allocation evidence fails closed.
- Startup records with a cross-overlay/reference/activation binding, wrong
  approval signer or interval, stale/future timestamp, duplicate/replayed
  attestation ID, invalid boundary timestamp, or non-distinct attestation
  trust anchor are rejected before execution.
- The canary cannot reuse the existing service identity or alter its service
  without a separate interruption approval.
