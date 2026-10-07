# Stellaris Historian

Stellaris Historian is a local companion application for Stellaris that watches Ironman save files and builds a historical record of your empire over time.

It is designed to turn a Stellaris campaign into a living historical archive, tracking major developments such as leaders, ships, technologies, worlds, combat events, and other campaign milestones.

## Current version

v0.0.42

## Features

- Watches Stellaris Ironman saves automatically
- Tracks historical changes between saves
- Builds campaign timelines
- Tracks leaders and notable people
- Tracks ships and fleet history
- Tracks technology progress
- Tracks worlds and empire development
- Tracks combat evidence and battle events
- Generates historical journal-style output
- Local web dashboard
- No cloud service required

## Requirements

- Windows
- Python 3
- Stellaris
- Steam version currently assumed by the default configuration

## Installation

1. Download the repository.
2. Extract it to a folder of your choice.
3. Copy `config.example.json`.
4. Rename the copy to `config.json`.
5. Edit `config.json` and set your Stellaris save location.

Example save path:

`C:\Program Files (x86)\Steam\userdata\YOUR_STEAM_USER_ID\281990\remote\save games`

6. Run `start.bat`.

Stellaris Historian will create its Python environment and install required dependencies if needed.

## Dashboard

Once running, the dashboard is available at:

`http://127.0.0.1:8766`

## Updating

If you downloaded the project using Git, update it with:

`git pull`

Then restart Stellaris Historian if the update requires it.

## Data and privacy

Stellaris Historian runs locally on your computer.

Your personal `config.json`, save files, logs, databases, backups, and other runtime data are excluded from this GitHub repository.

## Project status

Stellaris Historian is under active development.

The current codebase includes migration and historical tracking work through version 0.0.42.

## Author

PillBoxUK