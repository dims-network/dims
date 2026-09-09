"""Study scaffolding: create one, refresh its pinned core, verify it.

The API is `dims_case.core` and `dims_case.cli`. This file used to re-export
eight private names under public aliases -- `_write_vendor as write_vendor` and
so on -- which nothing imported: every caller, including the tests and the
wizard, reaches for the underscore names in `core`. An alias layer no caller
uses does not make an API public, it just gives the module two names for
everything and an absolute re-export that makes `core.py` harder to load by
path than it needs to be.
"""
