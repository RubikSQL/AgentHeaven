# Update Log

## v0.9.1.dev1 (2025-11-26)

- **_Feature_: `LLM` now supports tool-based interactions and `LLM.tooluse` which is compatible with `ToolSpec`**

- **_Feature_: `ToolSpec` now support decorating functions like `@ToolSpec(name="func")`**

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

- _Fix_: babel init now creates an empty _locales.jinja file

- _Fix_: babel translate now correctly handles multi-line strings in jinja templates

<br/>

## v0.9.1.dev0 (2025-11-21)

- Initial release

<br/>
