"""Confirmed adjacent defects from the one-pass Gryphon repair sweep, still open.

The OPTIONAL MATCH anchor-map and role-collision siblings are repaired and pinned in
`test_gryphon_construct_effect.py` and `test_gryphon.py`; the literal dimension key
(unified-systems-com/tap#1125) remains a strict expected failure until its repair lands.
"""

import pytest
from tap_grid.gryphon import explain_gryphon_raw
from tap_grid.service_types import WriteOperation
from tap_grid.services import write_batch

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "search_readonly"])


@pytest.mark.xfail(strict=True, reason="unified-systems-com/tap#1125: literal dimension key; repair is a separate PR")
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
