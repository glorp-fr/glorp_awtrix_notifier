"""Constants for the Glorp's Awtrix Notifier integration."""

DOMAIN = "glorp_awtrix_notifier"

SUBENTRY_TYPE_TARGET = "target"
SUBENTRY_TYPE_RULE = "rule"

# --- Target subentry data ---
CONF_NAME = "name"
CONF_MQTT_PREFIX = "mqtt_prefix"

# --- Rule subentry data ---
CONF_TARGET_NAMES = "target_names"
CONF_SHOW_TRIGGERS = "show_triggers"
CONF_SHOW_CONDITION = "show_condition"
CONF_TEXT_TEMPLATE = "text_template"
CONF_ICON_TEMPLATE = "icon_template"
CONF_COLOR = "color"
CONF_EFFECT = "effect"
CONF_HOLD = "hold"
CONF_REPEAT = "repeat"
CONF_CLEAR_TRIGGERS = "clear_triggers"
CONF_CLEAR_CONDITION = "clear_condition"

# --- Trigger dict fields (used inside CONF_SHOW_TRIGGERS / CONF_CLEAR_TRIGGERS) ---
CONF_TRIGGER_KIND = "kind"
CONF_INTERVAL_MINUTES = "interval_minutes"
CONF_AT = "at"
CONF_WEEKDAYS = "weekdays"
CONF_ENTITY_ID = "entity_id"

# --- Condition dict fields (used inside CONF_SHOW_CONDITION / CONF_CLEAR_CONDITION) ---
CONF_CONDITION_OP = "op"
CONF_CONDITION_VALUE = "value"

DEFAULT_COLOR = "FFFFFF"
DEFAULT_EFFECT = ""
DEFAULT_HOLD = False
DEFAULT_REPEAT = -1

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Decision reasons exposed on sensor.<rule>_raison.
REASON_OK = "ok"
REASON_CONDITION_NOT_MET = "condition_non_remplie"
REASON_ENTITY_UNAVAILABLE = "entite_indisponible"
REASON_TEMPLATE_ERROR_PREFIX = "erreur_template"

PLATFORMS = ["sensor"]
