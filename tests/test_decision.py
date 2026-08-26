"""Unit tests for the pure decision function. No Home Assistant needed."""

from custom_components.glorp_awtrix_notifier.const import (
    REASON_CONDITION_NOT_MET,
    REASON_ENTITY_UNAVAILABLE,
    REASON_OK,
)
from custom_components.glorp_awtrix_notifier.decision import decide
from custom_components.glorp_awtrix_notifier.models import (
    Action,
    ComparisonOp,
    Condition,
    Rule,
    Trigger,
    TriggerKind,
    TriggerSide,
)

_INTERVAL_TRIGGER = Trigger(kind=TriggerKind.INTERVAL, interval_minutes=5)


def _rule(**overrides) -> Rule:
    defaults = {
        "name": "Test rule",
        "target_names": ["Salon"],
        "show_triggers": [_INTERVAL_TRIGGER],
        "text_template": "hello",
        "icon_template": "1234",
    }
    return Rule(**{**defaults, **overrides})


def test_show_with_no_condition_always_shows():
    result = decide(_rule(), {}, TriggerSide.SHOW)
    assert result == (Action.SHOW, REASON_OK)


def test_clear_with_no_condition_always_clears():
    result = decide(_rule(), {}, TriggerSide.CLEAR)
    assert result == (Action.CLEAR, REASON_OK)


def test_above_condition_true_shows():
    rule = _rule(show_condition=Condition(entity_id="sensor.rain", op=ComparisonOp.ABOVE, value=0))
    result = decide(rule, {"sensor.rain": "1.5"}, TriggerSide.SHOW)
    assert result == (Action.SHOW, REASON_OK)


def test_above_condition_false_does_not_show():
    rule = _rule(show_condition=Condition(entity_id="sensor.rain", op=ComparisonOp.ABOVE, value=0))
    result = decide(rule, {"sensor.rain": "0"}, TriggerSide.SHOW)
    assert result == (Action.NONE, REASON_CONDITION_NOT_MET)


def test_below_condition_true_shows():
    rule = _rule(show_condition=Condition(entity_id="sensor.temp", op=ComparisonOp.BELOW, value=5))
    result = decide(rule, {"sensor.temp": "3"}, TriggerSide.SHOW)
    assert result == (Action.SHOW, REASON_OK)


def test_below_condition_false_does_not_show():
    rule = _rule(show_condition=Condition(entity_id="sensor.temp", op=ComparisonOp.BELOW, value=5))
    result = decide(rule, {"sensor.temp": "10"}, TriggerSide.SHOW)
    assert result == (Action.NONE, REASON_CONDITION_NOT_MET)


def test_equals_condition_true_shows():
    rule = _rule(show_condition=Condition(entity_id="binary_sensor.door", op=ComparisonOp.EQUALS, value="on"))
    result = decide(rule, {"binary_sensor.door": "on"}, TriggerSide.SHOW)
    assert result == (Action.SHOW, REASON_OK)


def test_equals_condition_false_does_not_show():
    rule = _rule(show_condition=Condition(entity_id="binary_sensor.door", op=ComparisonOp.EQUALS, value="on"))
    result = decide(rule, {"binary_sensor.door": "off"}, TriggerSide.SHOW)
    assert result == (Action.NONE, REASON_CONDITION_NOT_MET)


def test_missing_entity_is_unavailable():
    rule = _rule(show_condition=Condition(entity_id="sensor.rain", op=ComparisonOp.ABOVE, value=0))
    result = decide(rule, {}, TriggerSide.SHOW)
    assert result == (Action.NONE, REASON_ENTITY_UNAVAILABLE)


def test_unknown_state_is_unavailable():
    rule = _rule(show_condition=Condition(entity_id="sensor.rain", op=ComparisonOp.ABOVE, value=0))
    result = decide(rule, {"sensor.rain": "unknown"}, TriggerSide.SHOW)
    assert result == (Action.NONE, REASON_ENTITY_UNAVAILABLE)


def test_unavailable_state_is_unavailable():
    rule = _rule(show_condition=Condition(entity_id="sensor.rain", op=ComparisonOp.ABOVE, value=0))
    result = decide(rule, {"sensor.rain": "unavailable"}, TriggerSide.SHOW)
    assert result == (Action.NONE, REASON_ENTITY_UNAVAILABLE)


def test_non_numeric_state_with_above_op_is_unavailable():
    rule = _rule(show_condition=Condition(entity_id="sensor.rain", op=ComparisonOp.ABOVE, value=0))
    result = decide(rule, {"sensor.rain": "n/a"}, TriggerSide.SHOW)
    assert result == (Action.NONE, REASON_ENTITY_UNAVAILABLE)


def test_show_and_clear_conditions_are_evaluated_independently():
    # Only clear_condition matters for the CLEAR side, even if show_condition
    # on the same rule would also evaluate false for these inputs.
    rule = _rule(
        show_condition=Condition(entity_id="sensor.rain", op=ComparisonOp.ABOVE, value=0),
        clear_triggers=[_INTERVAL_TRIGGER],
        clear_condition=Condition(entity_id="sensor.rain", op=ComparisonOp.EQUALS, value="0"),
    )
    result = decide(rule, {"sensor.rain": "0"}, TriggerSide.CLEAR)
    assert result == (Action.CLEAR, REASON_OK)


def test_clear_side_ignores_show_condition():
    rule = _rule(
        show_condition=Condition(entity_id="sensor.rain", op=ComparisonOp.ABOVE, value=0),
        clear_triggers=[_INTERVAL_TRIGGER],
    )
    # clear_condition is None, so CLEAR always fires regardless of show_condition.
    result = decide(rule, {"sensor.rain": "0"}, TriggerSide.CLEAR)
    assert result == (Action.CLEAR, REASON_OK)
