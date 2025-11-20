# Known Limitations and TODOs

## Production Readiness

- [ ] AgentHeaven is in active experimental development. Features may change. NOT ready for stable deployment.

- [ ] LlamaIndex docs store all attributes as a single field, limiting query efficiency and often incurring max-length errors with large records.

- [ ] Vector queries (e.g., Milvus) typically limits the number of returned results, which disallows a full-scan over all records.

- [ ] Lazy imports not fully implemented, mongodb and other heavy dependencies may be imported even if not used.

- [ ] LiteLLM integration only supports general generation and embedding. Batch inference (for MTP, ToT), log-probs (for DeepConf), KV cache, and vision models are not yet supported.

- [ ] UKF Adaptor parser is poorly implemented, may fail on nested complex filters. To be refactored with manual, standardized parsing and backend-specific testing.

- [ ] Authority control is externally managed, no built-in support for user-based access control. The authority control requires more design considerations beyond simple user roles. Not planned in the near future, as it is almost always enterprise's responsibility for building or plugging-in their own, private authority control system.

- [ ] Imitator module not ready. To be re-designed.

- [ ] DAACKLEngine enable multi-thread safety, currently not implemented.

- [ ] Prompt and Tool UKFs to be self-contained, shipped as a standard database.

<br/>

## Engineering

- [ ] Contribution Guide and Community

- [ ] Documentation

- [ ] Demonstration

- [ ] Tutorials

- [ ] Refactor AI-generated Tests

<br/>
