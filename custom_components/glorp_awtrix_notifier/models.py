"""Pure data model for Glorp's Awtrix Notifier. No Home Assistant dependency."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from enum import Enum


@dataclass
class Target:
    """An Awtrix display: a friendly name plus its MQTT prefix."""

    name: str
    mqtt_prefix: str


class TriggerKind(Enum):
    INTERVAL = "interval"
    TIME_OF_DAY = "time_of_day"
    ENTITY_CHANGE = "entity_change"


@dataclass
class Trigger:
    kind: TriggerKind
    interval_minutes: int | None = None
    at: time | None = None
    weekdays: list[str] = field(default_factory=list)
    entity_id: str | None = None


class ComparisonOp(Enum):
    ABOVE = "above"
    BELOW = "below"
    EQUALS = "equals"


@dataclass
class Condition:
    entity_id: str
    op: ComparisonOp
    value: str | float


@dataclass
class Rule:
    name: str
    target_names: list[str]
    show_triggers: list[Trigger]
    text_template: str
    icon_template: str
    show_condition: Condition | None = None
    color: str = "FFFFFF"
    effect: str = ""
    hold: bool = False
    repeat: int = -1
    clear_triggers: list[Trigger] = field(default_factory=list)
    clear_condition: Condition | None = None


class TriggerSide(Enum):
    SHOW = "show"
    CLEAR = "clear"


class Action(Enum):
    SHOW = "show"
    CLEAR = "clear"
    NONE = "none"
