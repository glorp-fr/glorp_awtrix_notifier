"""Unit tests for MQTT payload construction. No Home Assistant needed."""

from custom_components.glorp_awtrix_notifier.models import Rule, Target, Trigger, TriggerKind
from custom_components.glorp_awtrix_notifier.publisher import build_clear_payload, build_show_payload, slugify

_INTERVAL_TRIGGER = Trigger(kind=TriggerKind.INTERVAL, interval_minutes=5)
_SALON = Target(name="Salon", mqtt_prefix="awtrix_salon")
_SALON_NG = Target(name="Salon", mqtt_prefix="awtrix_salon", firmware_type="ng")


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


def test_build_show_payload_topic_for_ng_target_uses_cmd_apps_pushed():
    topic, _ = build_show_payload(_rule(), _SALON_NG, "Pluie", "1234")
    assert topic == "awtrix_salon/cmd/apps/pushed/awtrix_pluie"


def test_build_show_payload_body_for_ng_target_renames_color_to_text_color_with_hash():
    rule = _rule(color="00FF00")
    _, payload = build_show_payload(rule, _SALON_NG, "Pluie", "1234")
    assert payload["textColor"] == "#00FF00"
    assert "color" not in payload


def test_build_show_payload_body_for_ng_target_does_not_double_prefix_hash_color():
    rule = _rule(color="#00FF00")
    _, payload = build_show_payload(rule, _SALON_NG, "Pluie", "1234")
    assert payload["textColor"] == "#00FF00"


def test_build_show_payload_body_for_ng_target_omits_hold():
    rule = _rule(hold=True)
    _, payload = build_show_payload(rule, _SALON_NG, "Pluie", "1234")
    assert "hold" not in payload


def test_build_show_payload_body_for_ng_target_maps_infinite_repeat_to_zero():
    rule = _rule(repeat=-1)
    _, payload = build_show_payload(rule, _SALON_NG, "Pluie", "1234")
    assert payload["repeat"] == 0


def test_build_show_payload_body_for_ng_target_passes_through_positive_repeat():
    rule = _rule(repeat=3)
    _, payload = build_show_payload(rule, _SALON_NG, "Pluie", "1234")
    assert payload["repeat"] == 3


def test_build_show_payload_body_for_ng_target_sets_fixed_icon_mode():
    _, payload = build_show_payload(_rule(), _SALON_NG, "Pluie", "1234")
    assert payload["iconMode"] == "fixed"
    assert "pushIcon" not in payload


def test_build_show_payload_body_for_ng_target_keeps_text_icon_effect():
    rule = _rule(effect="Fade")
    _, payload = build_show_payload(rule, _SALON_NG, "Pluie", "1234")
    assert payload["text"] == "Pluie"
    assert payload["icon"] == "1234"
    assert payload["effect"] == "Fade"


def test_build_clear_payload_for_ng_target_uses_ng_topic_with_empty_body():
    show_topic, _ = build_show_payload(_rule(), _SALON_NG, "Pluie", "1234")
    clear_topic, clear_payload = build_clear_payload(_rule(), _SALON_NG)
    assert clear_topic == show_topic
    assert clear_payload == {}
