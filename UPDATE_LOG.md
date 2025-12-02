# Update Log

## v0.9.2.dev0 (2025-12-02)

<<<<<<< HEAD
- **_Feature_: `utils.exts.auto*` functions now uses dynamic examples list, enabling cache-based imitation.**
=======
- **_Feature_: `utils.exts.auto*` functions now use dynamic examples list, enabling cache-based imitation.**
>>>>>>> bed508c (0.9.2.dev0 [release])

- **_Feature_: `KLEngine` now stores search args and returns in `r['kl'].metadata['search']` for each search result**

- _Feature_: `config copy` now supports copying all configs with user confirmation by passing no keyword arguments

- _Fix_: `BaseKLEngine.search` now respects the `_search` defaults when `include=None`

- _Fix_: `DAACKLEngine` now defaults to return `["id", "kl", "strs"]`, and correctly parses `strs`

- _Fix_: `VectorKLEngine` with custom `k_encoder` now properly skips the new `DummyUKFT` during encoding

- _Fix_: `VectorKLEngine` and `MongoKLEngine` now has safer batch encode/embed methods that handle empty lists

<br/>

## v0.9.1.dev1 (2025-11-26)

- **_Feature_: `LLM` now supports tool-based interactions and `LLM.tooluse` which is compatible with `ToolSpec`**

- **_Feature_: `ToolSpec` now supports decorating functions like `@ToolSpec(name="func")`**

- **_Deprecate_: `LLM`'s `n` parameter for batch inference is temporarily removed**

- **_Optimize_: Refactored dependency management with lazy imports**

- _Feature_: `KLStore` now supports `batch_get`, with `DatabaseKLStore` and `MongoKLStore` having efficient implementations

- _Feature_: `FacetKLEngine` and `MongoKLEngine` now supports `orderby` parameter in search methods

- _Feature_: `ConfigManager` now supports `config copy` and inheritance by other packages

- _Feature_: `ahvn session` bug fixes, safeguards, defaults and user experience improvements

- _Feature_: `UKF*TextType` now supports `max_length()`

- _Optimize_: Better inheritance behavior: ukf tags & type default

- _Optimize_: BaseUKF defaults to empty `content_composers` and `triggers` dict to reduce memory usage

- _Fix_: milvus vdb store collection was not fully loaded before dummy removal

- _Fix_: `babel init` now creates an empty `_locales.jinja` file if not existing

- _Fix_: `babel translate` now correctly handles multi-line strings in jinja templates

<br/>

## v0.9.1.dev0 (2025-11-21)

- Initial release

<br/>
