"""Parse story sources into domain Story objects."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from drama_forge.domain.story import (
    Character,
    Episode,
    Prop,
    Scene,
    Shot,
    Story,
    World,
)


def compile_story_from_dict(data: dict[str, Any]) -> Story:
    """Compile a structured dict into a Story domain object.

    Expected shape:
    {
      "title": str,
      "world": {"name": str, "style": str, "rules": [str]},
      "characters": [{"name": str, "appearance": str, ...}],
      "props": [{"name": str, "description": str}],
      "episodes": [{
        "title": str,
        "scenes": [{
          "location": str,
          "description": str,
          "characters": [name],
          "shots": [{"description": str, "dialogue": str, "duration_seconds": float,
                     "camera": str, "characters": [name]}]
        }]
      }]
    }

    Args:
        data: Structured story dictionary.

    Returns:
        Compiled Story domain object.
    """
    story = Story.create(title=str(data.get("title", "Untitled")))
    world_data = data.get("world") or {}
    if world_data:
        story.world = World.create(
            name=str(world_data.get("name", story.title)),
            style=str(world_data.get("style", "")),
            rules=list(world_data.get("rules", []) or []),
        )

    name_to_char: dict[str, Character] = {}
    for char_data in data.get("characters", []) or []:
        character = Character.create(
            name=str(char_data["name"]),
            appearance=str(char_data.get("appearance", "")),
            personality=str(char_data.get("personality", "")),
            voice_identity=str(char_data.get("voice_identity", "")),
            costume_state=str(char_data.get("costume_state", "")),
        )
        story.add_character(character)
        name_to_char[character.name] = character

    for prop_data in data.get("props", []) or []:
        prop = Prop.create(
            name=str(prop_data["name"]),
            description=str(prop_data.get("description", "")),
        )
        story.add_prop(prop)

    for ep_index, ep_data in enumerate(data.get("episodes", []) or [], start=1):
        episode = Episode.create(
            story_id=story.id,
            index=ep_index,
            title=str(ep_data.get("title", f"Episode {ep_index}")),
        )
        story.add_episode(episode)
        for sc_index, sc_data in enumerate(ep_data.get("scenes", []) or [], start=1):
            scene = Scene.create(
                episode_id=episode.id,
                index=sc_index,
                location=str(sc_data.get("location", "")),
                description=str(sc_data.get("description", "")),
            )
            episode.add_scene(scene)
            for char_name in sc_data.get("characters", []) or []:
                char = name_to_char.get(str(char_name))
                if char:
                    scene.character_ids.append(char.id)
            for sh_index, sh_data in enumerate(sc_data.get("shots", []) or [], start=1):
                shot = Shot.create(
                    scene_id=scene.id,
                    index=sh_index,
                    description=str(sh_data.get("description", "")),
                    dialogue=str(sh_data.get("dialogue", "")),
                    camera=str(sh_data.get("camera", "")),
                    duration_seconds=float(sh_data.get("duration_seconds", 3.0)),
                )
                for char_name in sh_data.get("characters", []) or []:
                    char = name_to_char.get(str(char_name))
                    if char and char.id not in shot.character_ids:
                        shot.character_ids.append(char.id)
                if not shot.character_ids:
                    shot.character_ids = list(scene.character_ids)
                scene.add_shot(shot)
            story.timeline.add(scene.id, sc_index, label=scene.location)
    return story


def parse_markdown_story(text: str) -> dict[str, str]:
    """Parse a minimal markdown story into shot descriptions.

    Supports headings:
    # Title
    ## Character: Name
    ## Scene: Location
    ### Shot: description

    Args:
        text: Markdown source.

    Returns:
        Dict with title and extracted shot lines (simple parser).
    """
    title = "Untitled"
    shots: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("### "):
            shots.append(line[4:].strip())
        elif line.startswith("- ") and shots:
            shots[-1] = f"{shots[-1]} {line[2:].strip()}"
    return {"title": title, "shots": shots}


def load_story_source(path: str | Path) -> Story:
    """Load a story from a JSON file path.

    Args:
        path: Path to story JSON.

    Returns:
        Compiled Story.
    """
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    return compile_story_from_dict(data)


_STORY_BLOCK = re.compile(
    r"^#\s+(?P<title>.+)$",
    re.MULTILINE,
)


def story_to_dict(story: Story) -> dict[str, Any]:
    """Serialize a story into a plain dict (for persistence/debug)."""
    return {
        "id": story.id,
        "title": story.title,
        "version": story.version,
        "characters": [
            {
                "id": c.id,
                "name": c.name,
                "appearance": c.appearance,
                "personality": c.personality,
            }
            for c in story.characters.values()
        ],
        "episodes": [
            {
                "id": ep.id,
                "title": ep.title,
                "index": ep.index,
                "scenes": [
                    {
                        "id": sc.id,
                        "index": sc.index,
                        "location": sc.location,
                        "character_ids": sc.character_ids,
                        "shots": [
                            {
                                "id": sh.id,
                                "index": sh.index,
                                "description": sh.description,
                                "dialogue": sh.dialogue,
                                "duration_seconds": sh.duration_seconds,
                                "character_ids": sh.character_ids,
                            }
                            for sh in sc.shots
                        ],
                    }
                    for sc in ep.scenes
                ],
            }
            for ep in story.episodes
        ],
    }
