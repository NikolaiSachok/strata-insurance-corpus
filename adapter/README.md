# adapter/

The [Strata-RAG](https://github.com/NikolaiSachok/Strata-RAG) source adapter — lets the engine mount this
corpus via its plugin seam without forking. This is the **public** demonstration of Strata-RAG's open-core
overlay pattern.

Planned: a self-registering plugin module that, at import time, calls `register_adapter(folder, AdapterCls)`
and `register_family(family, roster_stem)` — with **absolute** imports (`from rageval.sources.base import …`,
`register_adapter` from `rageval.sources.registry`, `register_family` from `rageval.roster`), per Strata-RAG's
documented `RAGEVAL_PLUGINS_DIR` convention.

Usage (once built):
```bash
pip install -e /path/to/Strata-RAG
RAGEVAL_PLUGINS_DIR=$(pwd)/adapter RAGENGINE_CORPUS_ROOT=$(pwd)/corpus \
  python -m rageval.ingest --dry-run
```

Implemented in M5. Empty until then.
