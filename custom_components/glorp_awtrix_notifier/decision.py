"""Pure decision logic. No Home Assistant dependency, unit tested without HA installed."""

from __future__ import annotations

from .const import REASON_CONDITION_NOT_MET, REASON_ENTITY_UNAVAILABLE, REASON_OK
from .models import Action, ComparisonOp, Rule, TriggerSide

_UNAVAILABLE_STATES = {None, "unknown", "unavailable"}


def decide(rule: Rule, inputs: dict[str, str | None], side: TriggerSide) -> tuple[Action, str]:
    """Decide whether a rule should show, clear, or do nothing for one trigger side.

    `inputs` maps entity_id to its already-resolved state (str) or None if the
    entity is unknown/unavailable. Only the condition for `side` is evaluated;
    the other side's condition is irrelevant to this call.
    """
    if side is TriggerSide.SHOW:
        condition = rule.show_condition
        action_if_true = Action.SHOW
    else:
        condition = rule.clear_condition
        action_if_true = Action.CLEAR

    if condition is None:
        return action_if_true, REASON_OK

    state = inputs.get(condition.entity_id)
    if state in _UNAVAILABLE_STATES:
        return Action.NONE, REASON_ENTITY_UNAVAILABLE

    if condition.op is ComparisonOp.EQUALS:
        matched = state == str(condition.value)
    else:
        try:
            state_value = float(state)
            threshold = float(condition.value)
        except ValueError:
            return Action.NONE, REASON_ENTITY_UNAVAILABLE
        matched = state_value > threshold if condition.op is ComparisonOp.ABOVE else state_value < threshold

    if matched:
        return action_if_true, REASON_OK
    return Action.NONE, REASON_CONDITION_NOT_MET
