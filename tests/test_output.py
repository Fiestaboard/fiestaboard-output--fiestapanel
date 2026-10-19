"""The FiestaPanel plugin: a board FiestaBoard draws, pulled by its viewer.

It writes no device — core stores each frame for the panel's viewers — so
what the plugin decides is which frames fit the board, and what it declares.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plugins.fiestapanel import FiestaPanelOutput
from plugins.fiestapanel.output import board_dimensions
from src.outputs.conformance import OutputConformanceSuite
from src.canvas.layer import CanvasLayer
from src.outputs.cells import frame_layers, project_for_output, project_message
from src.outputs.plugin_driver import OutputPluginDriver
from src.plugins import CancelToken
from src.plugins.manifest import load_manifest

PLUGIN_DIR = Path(__file__).resolve().parents[1]


def _grid(rows: int, cols: int, fill: int = 0) -> list[list[int]]:
    return [[fill] * cols for _ in range(rows)]


@pytest.fixture
def manifest():
    parsed, errors = load_manifest(PLUGIN_DIR / "manifest.json")
    assert not errors, errors
    return parsed


def _panel(manifest, config, board_id="p1") -> FiestaPanelOutput:
    plugin = FiestaPanelOutput(board_id, config)
    plugin.bind_manifest(manifest.output)
    return plugin


def test_the_plugin_is_conformant():
    report = OutputConformanceSuite(
        plugin_dir=PLUGIN_DIR,
        factory=lambda board_id, config, transport: FiestaPanelOutput(board_id, config),
        config={"device_type": "panel", "grid_rows": 12, "grid_cols": 29},
    ).assert_conformant()
    assert report.plugin_id == "fiestapanel"
    assert any(skip.startswith("write_result") for skip in report.skipped), "a pull output has no device to fail"


class TestDimensions:
    @pytest.mark.parametrize(
        ("config", "dims"),
        [
            ({"device_type": "flagship"}, (6, 22)),
            ({"device_type": "note"}, (3, 15)),
            ({"device_type": "note_array", "notes_wide": 2, "notes_tall": 4}, (12, 30)),
            ({"device_type": "panel", "grid_rows": 12, "grid_cols": 29}, (12, 29)),
            ({"device_type": "panel", "grid_rows": 1, "grid_cols": 999}, (3, 128)),
        ],
    )
    def test_the_board_shape(self, config, dims):
        assert board_dimensions(config) == dims

    @pytest.mark.parametrize("grid", [{"grid_rows": None, "grid_cols": 29}, {"grid_rows": True, "grid_cols": 29}])
    def test_a_panel_needs_an_integer_grid(self, grid):
        with pytest.raises(ValueError, match="A panel grid needs an integer grid_rows"):
            board_dimensions({"device_type": "panel", **grid})

    def test_an_unknown_shape_is_refused(self):
        with pytest.raises(ValueError, match="Unknown device type: hexagon"):
            board_dimensions({"device_type": "hexagon"})


class TestConfigFromBoard:
    def test_every_board_builds_from_its_shape(self):
        config = FiestaPanelOutput.config_from_board(
            {"id": "p1", "api_mode": "virtual", "device_type": "note_array", "notes_wide": "2", "notes_tall": 4}
        )
        assert config == {
            "device_type": "note_array",
            "notes_wide": 2,
            "notes_tall": 4,
            "grid_rows": None,
            "grid_cols": None,
        }

    def test_missing_fields_get_the_platform_defaults(self):
        assert FiestaPanelOutput.config_from_board({"grid_rows": "x", "notes_wide": True}) == {
            "device_type": "flagship",
            "notes_wide": 1,
            "notes_tall": 1,
            "grid_rows": None,
            "grid_cols": None,
        }


class TestWrites:
    def test_a_frame_of_the_boards_shape_is_kept_by_core(self, manifest):
        panel = _panel(manifest, {"device_type": "note"})
        result = panel.write(_grid(3, 15, 7), native=None, cancel=CancelToken())
        assert (result.success, result.was_sent) == (True, True)

    def test_a_frame_of_another_shape_is_refused(self, manifest):
        panel = _panel(manifest, {"device_type": "note"})
        assert panel.accepts_frame(_grid(6, 22)) is False
        assert panel.accepts_frame("nope") is False
        result = panel.write(_grid(6, 22), native=None, cancel=CancelToken())
        assert (result.success, result.was_sent) == (False, False)

    def test_rich_frame_of_another_shape_is_refused(self, manifest):
        panel = _panel(manifest, {"device_type": "note"})
        driver = _driver(manifest, led=True)
        rich = project_message("a", 6, 22, driver.plugin.character_set).cells
        result = panel.write_cells(rich, native=None, cancel=CancelToken())
        assert (result.success, result.was_sent) == (False, False)


class TestDeclarations:
    def test_a_pulled_screen_with_no_native_strategy(self, manifest):
        caps = FiestaPanelOutput.declared_capabilities(manifest.output)
        assert (caps.technology, caps.delivery, caps.animation, caps.native_transitions) == (
            "screen",
            "pull",
            "stream",
            frozenset(),
        )

    def test_a_board_reads_back_cheaply_from_cores_store(self, manifest):
        read_back = _panel(manifest, {"device_type": "flagship"}).capabilities().read_back
        assert (read_back.supported, read_back.cost) == (True, "cheap")

    def test_capabilities_need_a_bound_manifest(self):
        with pytest.raises(RuntimeError):
            FiestaPanelOutput("p1", {"device_type": "flagship"}).capabilities()

    def test_identity_and_connection(self, manifest):
        panel = _panel(manifest, {"device_type": "panel", "grid_rows": 8, "grid_cols": 30})
        assert panel.device_key() == "virtual:p1"
        assert _panel(manifest, {"device_type": "note"}, board_id=None).device_key().startswith("virtual:anonymous-")
        assert panel.board_geometry == (8, 30)
        assert panel.connection_label() == "Local API"
        assert panel.test_connection() is True
        assert panel.check_connection().success is True

    def test_it_declares_both_render_styles(self, manifest):
        assert manifest.output.device_model_ids == ("fiestapanel_split_flap", "fiestapanel_led_matrix")


def _driver(manifest, *, led):
    panel = _panel(manifest, {"device_type": "panel", "grid_rows": 12, "grid_cols": 32})
    panel.bind_board(device_model=manifest.output.model(1 if led else 0), geometry=(12, 32))
    return OutputPluginDriver(panel, character_set=panel.character_set, first_party=True)


def test_led_projection_retains_rich_text_and_pixel_layers_in_core_store(manifest):
    driver = _driver(manifest, led=True)
    red = CanvasLayer(2, 3, 1, 1, bytes([255, 0, 0, 255]))
    grid, kwargs = project_for_output(driver, "{red:a}", 12, 32, layers=[red])
    assert driver.render(grid, **kwargs) == (True, True)
    cached = driver._frames.cells
    assert cached is not None
    assert (cached[0][0].value, cached[0][0].color) == ("a", "red")
    assert frame_layers(cached) == (red,)


def test_pixel_only_changes_and_removal_are_new_frames_but_duplicates_are_not(manifest):
    driver = _driver(manifest, led=True)
    red = CanvasLayer(0, 0, 1, 1, bytes([255, 0, 0, 255]))
    blue = CanvasLayer(0, 0, 1, 1, bytes([0, 0, 255, 255]))
    for layers in ([red], [blue], []):
        grid, kwargs = project_for_output(driver, "", 12, 32, layers=layers)
        assert driver.render(grid, **kwargs) == (True, True)
        assert frame_layers(driver._frames.cells) == tuple(layers)
        assert driver.render(grid, **kwargs) == (True, False)


def test_split_flap_projection_remains_integer_text_without_layers(manifest):
    driver = _driver(manifest, led=False)
    red = CanvasLayer(0, 0, 1, 1, bytes([255, 0, 0, 255]))
    grid, kwargs = project_for_output(driver, "a{red}", 12, 32, layers=[red])
    assert kwargs == {}
    assert grid[0][:2] == [1, 63]
    assert driver.render(grid, **kwargs) == (True, True)
    assert driver._frames.characters == grid
    assert driver._frames.cells is None
