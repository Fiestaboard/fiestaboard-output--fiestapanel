# FiestaPanel Plugin

Show your FiestaBoard pages full-screen on any TV or browser, as a board FiestaBoard draws itself.

![FiestaPanel Display](./docs/board-display.png)

**→ [Setup Guide](./docs/SETUP.md)**

## Overview

The FiestaPanel plugin is an output plugin with no hardware behind it. FiestaBoard keeps each frame it renders for the board, and the panel's viewer — the FiestaBoard TV app or a browser — fetches it from `GET /panel/{id}/frame` and draws it, as split flaps or as an LED matrix. The plugin decides which frames fit the board; FiestaBoard does everything else.

## Template Variables

An output plugin exposes no template variables. Every page and template renders on a panel; the panel's grid, sized from the screen, decides how much fits.

## Example Templates

A clock line on a panel:

```jinja
{center}{violet} GOOD MORNING {violet}
{center}{{date_time.time}}
```

## Configuration

A FiestaPanel has no connection to configure. Its shape belongs to the board:

| Setting | Type | Description |
|---------|------|-------------|
| `device_type` | `flagship` \| `note` \| `note_array` \| `panel` | The board's shape. A panel created from a TV is `panel`. |
| `grid_rows` / `grid_cols` | integer | A `panel`'s grid, 3–96 rows by 15–128 columns. |
| `notes_wide` / `notes_tall` | integer | A `note_array`-shaped panel's size in Notes. |

## Features

- Pull delivery: nothing is pushed to a device; the viewer fetches the last frame
- A frame of the wrong shape (after the panel was re-fit to a new screen) is never served
- Two looks from one board: split-flap and LED matrix (`fiestapanel_split_flap`, `fiestapanel_led_matrix`)
- No send floor and no connection to fail

## Development

Tests run against a FiestaBoard core checkout that has the output-plugin API:

```bash
./run_tests.sh /path/to/FiestaBoard
```

The script builds an ignored `plugins/<id>` import scaffold so the tests import this plugin as
`plugins.<id>`, the name FiestaBoard gives it. The suite includes FiestaBoard's
`OutputConformanceSuite`, runs behind a network fence that allows loopback only, and needs 80%
coverage.

CI (`.github/workflows/ci.yml`) runs on every push and pull request to `main`, and nightly:

- **versions**: `package.json` and `manifest.json` carry the same version. `package.json`
  publishes only the device data (`output/*.json`) so FiestaUI can depend on it; bump both
  together.
- **test**: checks out FiestaBoard core and runs `./run_tests.sh` on Python 3.11. The default core
  ref is the top branch of the unmerged output-plugins stack until it reaches `next`; the
  `core_ref` input of a manual run picks another branch, tag or commit.

FiestaBoard bundles this plugin at the commit pinned in its `outputs.lock.json`. A release here
reaches users when a pull request to FiestaBoard bumps that pin (`commit` and `tree_sha256`; print
the digest with `python scripts/seed_outputs.py digest <clean checkout>`).

## Author

FiestaBoard
