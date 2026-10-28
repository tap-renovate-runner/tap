"""Confirmed adjacent defects from the one-pass Gryphon repair sweep.

Registered locally in docs/misc/gryphon-query-defect-repair-2026-10-27.md.
External issue creation was rejected by automatic approval review; these strict
xfails preserve the reproductions until publication is explicitly approved.
"""

import pytest
from tap_grid.gryphon import explain_gryphon_raw
from tap_grid.exceptions import SearchExecutionError
from tap_grid.service_types import WriteOperation
from tap_grid.services import write_batch

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "search_readonly"])


@pytest.mark.xfail(
    strict=True, reason="pending-optional-anchor-map: documented local sibling; not repaired in this pass"
)
def test_optional_repeated_anchor_map():
    a = explain_gryphon_raw(
        'MATCH (t:batch) OPTIONAL MATCH (t {name: "required"})-[:X]->(w:batch) RETURN t.entity_id AS id, COUNT(w) AS c',
        {},
    )["sql"]
    b = explain_gryphon_raw(
        "MATCH (t:batch) OPTIONAL MATCH (t)-[:X]->(w:batch) RETURN t.entity_id AS id, COUNT(w) AS c", {}
    )["sql"]
    lhs = [(st.sql, repr(st.params)) for st in a.statements]
    rhs = [(st.sql, repr(st.params)) for st in b.statements]
    assert lhs and rhs
    assert lhs != rhs, "OPTIONAL repeated anchor map accepted and dropped"


@pytest.mark.xfail(
    strict=True, reason="pending-optional-role-collision: documented local sibling; not repaired in this pass"
)
@pytest.mark.parametrize(
    "query",
    [
        "MATCH (t:batch) OPTIONAL MATCH (t)-[w:X]->(w:batch) RETURN t.entity_id AS id, COUNT(w) AS c",
        "MATCH (t:batch) OPTIONAL MATCH (t)-[t:X]->(w:batch) RETURN t.entity_id AS id, COUNT(w) AS c",
    ],
)
def test_optional_cross_role_collision(query):
    with pytest.raises(SearchExecutionError):
        explain_gryphon_raw(query, {})


@pytest.mark.xfail(
    strict=True, reason="pending-literal-dimension-key: documented local sibling; not repaired in this pass"
)
def test_literal_dimension_key():
    result = write_batch(
        [
            WriteOperation(
                verb="create_node",
                type_slug="grid_fixtures__node",
                payload={"name": "Literal dimension target", "kind": "fixture"},
                dimensions={"tap__cloud": "aws"},
            )
        ],
        batch_name="Literal dimension key probe",
        batch_description="Probe one authored flat key through named service batch",
    )
    assert result.success, result
    cap = explain_gryphon_raw('MATCH (n) WHERE n.dimensions["tap__cloud"] = "aws" RETURN n', {})
    assert cap["sql"].statements
    assert any(str(node["entity_id"]) == str(result.results[0].entity_id) for node in cap["envelope"]["nodes"])
