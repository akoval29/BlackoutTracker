Audio registry for BlackoutTracker

registry.json: 36 stable message IDs, each with ua/en/de translations.
Paths are relative to assets/audio, NOT the current working directory.
Example: registry["messages"]["power.outage_in_5_minutes"]["translations"]["ua"]["path"]
returns ua/power_outage_in_5_minutes.mp3.
Resolve with ASSETS_DIRECTORY / "audio" / translation["path"].

Use introId to optionally prepend common.attention in the same language.
Play the introduction once for a grouped sequence, not before every item.
The registry describes audio assets; it does not define alert triggering rules.
The ua key matches the existing JSON; its standard locale is uk-UA.
Text is matched using source JSON and the import manifest. Spoken content has
not been manually verified. Durations and file integrity have been checked.

provenance/ retains source JSON, import metadata and verification reports.
json-backups/ retains the originals from the separate Patcher project.
Playback uses Qt Multimedia and this registry. All audio filenames use .mp3,
matching their MP3 codec (verified with ffprobe).
No conversion was performed. The legacy WAV files are no longer used.
Use play_message(message_id, language) or play_warning(minutes, language).
Both are called on the Qt application thread; ua is the default language.
Intro and message are queued together and cannot be interleaved.
Portable builds include only registry.json and ua/en/de audio folders.
