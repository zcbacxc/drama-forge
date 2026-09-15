# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Capability registry: named production capabilities and their contracts.

Capabilities are provider-agnostic. A capability names what kind of work a
node performs (image generation, audio generation, vision evaluation, ...)
independently of which provider fulfils it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CapabilitySpec:
    """Contract for one production capability.

    Attributes:
        name: Stable capability identifier used in generation specs.
        input_types: Accepted input media/kind labels.
        output_types: Produced output media/kind labels.
        supports_continuity: Whether the capability participates in continuity checks.
        description: Human-readable purpose of the capability.
    """

    name: str
    input_types: list[str] = field(default_factory=list)
    output_types: list[str] = field(default_factory=list)
    supports_continuity: bool = False
    description: str = ""

    def accepts(self, media_type: str) -> bool:
        """Return True if the given media type is an accepted input.

        Args:
                    media_type: str

        Returns:
                    bool
        """
        return media_type in self.input_types

    def produces(self, media_type: str) -> bool:
        """Return True if the given media type is a declared output.

        Args:
                    media_type: str

        Returns:
                    bool
        """
        return media_type in self.output_types


class CapabilityRegistry:
    """Registry of capability specs available to the production graph."""

    def __init__(self) -> None:
        """__init__.

        Args:
                    None.
        """
        self._specs: dict[str, CapabilitySpec] = {}

    def register(self, spec: CapabilitySpec) -> CapabilitySpec:
        """Register a capability spec.

        Args:
            spec: Capability specification to register.

        Returns:
            The registered spec.

        Raises:
            ValueError: If a different spec with the same name already exists.
        """
        existing = self._specs.get(spec.name)
        if existing is not None and existing != spec:
            raise ValueError(f"capability already registered: {spec.name}")
        self._specs[spec.name] = spec
        return spec

    def get(self, name: str) -> CapabilitySpec | None:
        """Look up a capability by name.

        Args:
                    name: str

        Returns:
                    CapabilitySpec | None
        """
        return self._specs.get(name)

    def supports(self, name: str) -> bool:
        """Return True if the capability name is registered.

        Args:
                    name: str

        Returns:
                    bool
        """
        return name in self._specs

    def list_capabilities(self) -> list[str]:
        """Return all registered capability names sorted for determinism.

        Returns:
                    list[str]
        """
        return sorted(self._specs)

    def continuity_capable(self) -> list[str]:
        """Return names of capabilities that participate in continuity checks.

        Returns:
                    list[str]
        """
        return sorted(
            name for name, spec in self._specs.items() if spec.supports_continuity
        )

    def require(self, name: str) -> CapabilitySpec:
        """Return a capability or raise if unknown.

        Args:
            name: Capability name.

        Returns:
            The registered CapabilitySpec.

        Raises:
            KeyError: If the capability is not registered.
        """
        spec = self._specs.get(name)
        if spec is None:
            raise KeyError(f"unknown capability: {name}")
        return spec


def default_capability_registry() -> CapabilityRegistry:
    """Build the default Drama Forge capability registry.

    Returns:
        Registry pre-populated with the Stage F named capabilities.
    """
    registry = CapabilityRegistry()
    registry.register(
        CapabilitySpec(
            name="text_generation",
            input_types=["text"],
            output_types=["text"],
            supports_continuity=False,
            description="Generate or rewrite textual content.",
        )
    )
    registry.register(
        CapabilitySpec(
            name="image_generation",
            input_types=["text", "image"],
            output_types=["image"],
            supports_continuity=True,
            description="Generate a still image (character or scene reference).",
        )
    )
    registry.register(
        CapabilitySpec(
            name="video_generation",
            input_types=["text", "image", "audio"],
            output_types=["video"],
            supports_continuity=True,
            description="Generate video shot candidates.",
        )
    )
    registry.register(
        CapabilitySpec(
            name="audio_generation",
            input_types=["text"],
            output_types=["audio"],
            supports_continuity=True,
            description="Generate audio (music, ambience, narration).",
        )
    )
    registry.register(
        CapabilitySpec(
            name="vision_evaluation",
            input_types=["image", "video"],
            output_types=["json"],
            supports_continuity=True,
            description="Evaluate visual candidates with vision models.",
        )
    )
    registry.register(
        CapabilitySpec(
            name="image_evaluation",
            input_types=["image"],
            output_types=["json"],
            supports_continuity=True,
            description="Evaluate still-image candidates.",
        )
    )
    registry.register(
        CapabilitySpec(
            name="video_evaluation",
            input_types=["video"],
            output_types=["json"],
            supports_continuity=True,
            description="Evaluate video candidates.",
        )
    )
    registry.register(
        CapabilitySpec(
            name="continuity_validation",
            input_types=["timeline", "candidates"],
            output_types=["json"],
            supports_continuity=True,
            description="Validate character/scene continuity across selected takes.",
        )
    )
    registry.register(
        CapabilitySpec(
            name="timeline_render",
            input_types=["timeline", "video", "audio"],
            output_types=["timeline"],
            supports_continuity=False,
            description="Assemble and render a canonical timeline with time offsets.",
        )
    )
    registry.register(
        CapabilitySpec(
            name="dialogue_audio",
            input_types=["text"],
            output_types=["audio"],
            supports_continuity=True,
            description="Generate character dialogue audio aligned to a shot.",
        )
    )
    return registry
