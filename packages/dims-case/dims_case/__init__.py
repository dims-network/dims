"""Study scaffolding: create one, refresh its pinned core, verify it."""
from dims_case.core import (  # noqa: F401
    CORE_ROOT, RESTRICTED, SHARED_STEPS,
    _write_vendor as write_vendor,
    _write_index as write_index,
    _write_workflows as write_workflows,
    _register_study_tabs as register_study_tabs,
    _install_private_bits as install_private_bits,
    _write_hooks as write_hooks,
    _dir_hash as dir_hash,
    _core_version as core_version,
    verify_vendor,
)
