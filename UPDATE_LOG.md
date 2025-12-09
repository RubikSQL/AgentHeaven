# Update Log

## v0.9.2.dev1 (2025-12-09)

- **_Feature_: new `ScanKLEngine`, which brute-force scans all entries in the KLStore for search, useful for small datasets and testing**

- **_Feature_: `HEAVEN_KB` which stores built-in ahvn ukfs, as a first attempt towards AgentHeaven's self-containment**

- **_Feature_: `dmerge` (used in ConfigManager) now supports overwriting nested dictionaries with the special key `_OVERWRITE_`**

- **_Feature_: Progress bar utils is added to AgentHeaven utils for a unified callback progress reporting system**

- **_Feature_: `system/prompt.jinja` now supports `toolspecs` to render tool specifications in prompts with instruction on text-based function calling**

- **_Feature_: `autocode/autofunc/autotask` prompts are converted to `PromptUKFT`, which now supports `format` and `bind` and have altered composers**

- **_Feature_: `BaseUKF` now supports `get` to retrieve nested values from `content_resources` using dot-separated key paths**

- **_Fix_: LLM tool calling now properly parses `index` (missing for backends like `vllm`) for merging tool call deltas**

- _Feature_: `ToolSpec` now supports `to_function` to convert a `ToolSpec` back to a callable function with proper signature

- _Feature_: `funcwrap` utility added to wrap a function with the signature and metadata of another function

- _Feature_: `KLBase` now supports `default_engine` which is used when no engine is specified in `search`

- _Deprecate_: `KLBase` now interprets CRUD to `storages` and `engines` separately; if both are None, all storages and engines are used; if one is None, it is set to empty list if the other is non-empty, otherwise all.

- _Deprecate_: `klengine.batch_size` -> `klengine.sync_batch_size` for sync operations to clarify usage

- _Fix_: fixed `auto*` creating a different function signature than expected when `bind` is used, causing `Cache.memoize` to fail

- _Fix_: `system/prompt.jinja` now guarantees two blank lines between sections, even when some sections are omitted

- _Fix_: updated default LLM presets

- _Fix_: `ahvn chat` and `ahvn session` now default to appropriate presets (`chat`) if none specified

<br/>

## v0.9.2.dev0 (2025-12-02)

- **_Feature_: `utils.exts.auto*` functions now use a dynamic examples list, enabling cache-based imitation**

- **_Feature_: `KLEngine` now stores search args and returns in `r['kl'].metadata['search']` for each search result**

- _Feature_: `config copy` now supports copying all configs with user confirmation by passing no keyword arguments

- _Deprecate_: `ToolSpec.jsonschema` disabled strict mode to be compatible with optional parameters

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
