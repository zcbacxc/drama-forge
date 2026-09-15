"""Story content model: what to produce (not how to execute)."""

from __future__ import annotations

from dataclasses import dataclass, field

from drama_forge.domain.common import MetadataBag, new_id, stable_hash


def _stable_entity_id(prefix: str, *parts: object) -> str:
    """Build a content-stable entity id from natural key parts."""
    return f"{prefix}_{stable_hash({'parts': [str(p) for p in parts]})[:12]}"


@dataclass(slots=True)
class Character:
    """Stable character identity in a story."""

    id: str
    name: str
    appearance: str = ""
    personality: str = ""
    voice_identity: str = ""
    costume_state: str = ""
    metadata: MetadataBag = field(default_factory=MetadataBag)

    @classmethod
    def create(cls, name: str, **kwargs: object) -> Character:
        """Create a character with a content-stable id."""
        return cls(id=_stable_entity_id("char", name), name=name, **kwargs)  # type: ignore[arg-type]


@dataclass(slots=True)
class Prop:
    """Key prop object in a story."""

    id: str
    name: str
    description: str = ""
    metadata: MetadataBag = field(default_factory=MetadataBag)

    @classmethod
    def create(cls, name: str, **kwargs: object) -> Prop:
        """Create a prop with a generated id."""
        return cls(id=new_id("prop"), name=name, **kwargs)  # type: ignore[arg-type]


@dataclass(slots=True)
class World:
    """World rules and global constraints."""

    id: str
    name: str
    style: str = ""
    rules: list[str] = field(default_factory=list)
    metadata: MetadataBag = field(default_factory=MetadataBag)

    @classmethod
    def create(cls, name: str, **kwargs: object) -> World:
        """Create a world with a generated id."""
        return cls(id=new_id("world"), name=name, **kwargs)  # type: ignore[arg-type]


@dataclass(slots=True)
class Shot:
    """Minimal production unit inside a scene."""

    id: str
    scene_id: str
    index: int
    description: str = ""
    dialogue: str = ""
    camera: str = ""
    duration_seconds: float = 3.0
    character_ids: list[str] = field(default_factory=list)
    metadata: MetadataBag = field(default_factory=MetadataBag)

    @classmethod
    def create(
        cls,
        scene_id: str,
        index: int,
        description: str = "",
        **kwargs: object,
    ) -> Shot:
        """Create a shot bound to a scene."""
        return cls(
            id=_stable_entity_id("shot", scene_id, index),
            scene_id=scene_id,
            index=index,
            description=description,
            **kwargs,  # type: ignore[arg-type]
        )


@dataclass(slots=True)
class Scene:
    """Scene containing shots and participants."""

    id: str
    episode_id: str
    index: int
    location: str = ""
    description: str = ""
    character_ids: list[str] = field(default_factory=list)
    shots: list[Shot] = field(default_factory=list)
    metadata: MetadataBag = field(default_factory=MetadataBag)

    @classmethod
    def create(cls, episode_id: str, index: int, **kwargs: object) -> Scene:
        """Create a scene bound to an episode."""
        return cls(
            id=_stable_entity_id("scene", episode_id, index),
            episode_id=episode_id,
            index=index,
            **kwargs,  # type: ignore[arg-type]
        )

    def add_shot(self, shot: Shot) -> Shot:
        """Append a shot to this scene."""
        shot.scene_id = self.id
        self.shots.append(shot)
        return shot


@dataclass(slots=True)
class Episode:
    """Episode containing scenes."""

    id: str
    story_id: str
    index: int
    title: str = ""
    scenes: list[Scene] = field(default_factory=list)
    metadata: MetadataBag = field(default_factory=MetadataBag)

    @classmethod
    def create(cls, story_id: str, index: int, title: str = "") -> Episode:
        """Create an episode bound to a story."""
        return cls(
            id=_stable_entity_id("ep", story_id, index),
            story_id=story_id,
            index=index,
            title=title,
        )

    def add_scene(self, scene: Scene) -> Scene:
        """Append a scene to this episode."""
        scene.episode_id = self.id
        self.scenes.append(scene)
        return scene


@dataclass(slots=True)
class Event:
    """Plot event in the story graph."""

    id: str
    description: str
    character_ids: list[str] = field(default_factory=list)
    scene_id: str | None = None
    metadata: MetadataBag = field(default_factory=MetadataBag)

    @classmethod
    def create(cls, description: str, **kwargs: object) -> Event:
        """Create a story event."""
        return cls(id=new_id("evt"), description=description, **kwargs)  # type: ignore[arg-type]


@dataclass(slots=True)
class Relationship:
    """Directed relationship between story entities."""

    id: str
    source_id: str
    target_id: str
    kind: str
    metadata: MetadataBag = field(default_factory=MetadataBag)

    @classmethod
    def create(cls, source_id: str, target_id: str, kind: str) -> Relationship:
        """Create a relationship edge."""
        return cls(
            id=new_id("rel"),
            source_id=source_id,
            target_id=target_id,
            kind=kind,
        )


@dataclass(slots=True)
class TimelineEntry:
    """Narrative time ordering entry."""

    entity_id: str
    order: int
    label: str = ""


@dataclass(slots=True)
class StoryTimeline:
    """Story-level temporal ordering (not production timeline)."""

    entries: list[TimelineEntry] = field(default_factory=list)

    def add(self, entity_id: str, order: int, label: str = "") -> TimelineEntry:
        """Add an ordering entry."""
        entry = TimelineEntry(entity_id=entity_id, order=order, label=label)
        self.entries.append(entry)
        self.entries.sort(key=lambda e: e.order)
        return entry


@dataclass(slots=True)
class Story:
    """Root content object describing a drama work."""

    id: str
    title: str
    version: int = 1
    world: World | None = None
    characters: dict[str, Character] = field(default_factory=dict)
    props: dict[str, Prop] = field(default_factory=dict)
    episodes: list[Episode] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    timeline: StoryTimeline = field(default_factory=StoryTimeline)
    metadata: MetadataBag = field(default_factory=MetadataBag)

    @classmethod
    def create(cls, title: str, **kwargs: object) -> Story:
        """Create a story root object."""
        return cls(
            id=_stable_entity_id("story", title),
            title=title,
            **kwargs,  # type: ignore[arg-type]
        )

    def add_character(self, character: Character) -> Character:
        """Register a character on the story."""
        self.characters[character.id] = character
        return character

    def add_prop(self, prop: Prop) -> Prop:
        """Register a prop on the story."""
        self.props[prop.id] = prop
        return prop

    def add_episode(self, episode: Episode) -> Episode:
        """Append an episode."""
        episode.story_id = self.id
        self.episodes.append(episode)
        return episode

    def add_event(self, event: Event) -> Event:
        """Append a plot event."""
        self.events.append(event)
        return event

    def add_relationship(self, relationship: Relationship) -> Relationship:
        """Append a relationship."""
        self.relationships.append(relationship)
        return relationship

    def all_shots(self) -> list[Shot]:
        """Return every shot in episode/scene order."""
        shots: list[Shot] = []
        for episode in self.episodes:
            for scene in episode.scenes:
                shots.extend(scene.shots)
        return shots

    def fingerprint(self) -> str:
        """Compute story content fingerprint for cache/reuse checks."""
        return stable_hash(
            {
                "id": self.id,
                "version": self.version,
                "title": self.title,
                "characters": sorted(c.name for c in self.characters.values()),
                "shots": [
                    {"scene": s.scene_id, "index": s.index, "desc": s.description}
                    for s in self.all_shots()
                ],
            }
        )
