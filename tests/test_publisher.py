"""Unit tests for MQTT payload construction. No Home Assistant needed."""

from custom_components.glorp_awtrix_notifier.models import Rule, Target, Trigger, TriggerKind
from custom_components.glorp_awtrix_notifier.publisher import build_clear_payload, build_show_payload, slugify

_INTERVAL_TRIGGER = Trigger(kind=TriggerKind.INTERVAL, interval_minutes=5)
_SALON = Target(name="Salon", mqtt_prefix="awtrix_salon")


def _rule(**overrides) -> Rule:
    defaults = {
        "name": "Awtrix pluie",
        "target_names": ["Salon"],
        "show_triggers": [_INTERVAL_TRIGGER],
        "text_template": "Pluie",
        "icon_template": "1234",
    }
    return Rule(**{**defaults, **overrides})


def test_build_show_payload_topic_uses_target_prefix_and_slugified_rule_name():
    topic, _ = build_show_payload(_rule(), _SALON, "Pluie", "1234")
    assert topic == "awtrix_salon/custom/awtrix_pluie"


def test_build_show_payload_body_carries_rendered_content_and_rule_options():
    rule = _rule(color="00FF00", effect="Fade", hold=True, repeat=3)
    _, payload = build_show_payload(rule, _SALON, "Pluie", "1234")
    assert payload == {
        "text": "Pluie",
        "icon": "1234",
        "color": "00FF00",
        "repeat": 3,
        "effect": "Fade",
        "hold": True,
    }


def test_build_clear_payload_uses_same_topic_as_show_with_empty_body():
    show_topic, _ = build_show_payload(_rule(), _SALON, "Pluie", "1234")
    clear_topic, clear_payload = build_clear_payload(_rule(), _SALON)
    assert clear_topic == show_topic
    assert clear_payload == {}


def test_two_rules_on_the_same_target_get_different_topics():
    topic_a, _ = build_show_payload(_rule(name="Awtrix pluie"), _SALON, "x", "y")
    topic_b, _ = build_show_payload(_rule(name="Awtrix bin"), _SALON, "x", "y")
    assert topic_a != topic_b


def test_slugify_lowercases_and_replaces_non_alphanumeric_runs():
    assert slugify("Awtrix - Power usage!") == "awtrix_power_usage"


def test_slugify_strips_leading_and_trailing_separators():
    assert slugify("  Salon  ") == "salon"


def test_slugify_never_returns_empty_string():
    assert slugify("---") == "_"
