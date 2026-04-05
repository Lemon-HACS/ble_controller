"""BLE Controller 통합 상수 정의."""

DOMAIN = "ble_controller"

CONF_SERVICE_UUID = "service_uuid"
CONF_CHAR_UUID = "char_uuid"
CONF_WRITE_WITH_RESPONSE = "write_with_response"
CONF_KEEP_ALIVE = "keep_alive"
CONF_ENTITY_TYPE = "entity_type"

# switch
CONF_DATA_ON = "data_on"
CONF_DATA_OFF = "data_off"

# button
CONF_DATA_PRESS = "data_press"

# select
CONF_OPTIONS = "options"  # list of {"label": str, "data": str(hex)}

# notify (공통, 선택)
CONF_NOTIFY_UUID = "notify_uuid"
CONF_NOTIFY_ON_PATTERN = "notify_on_pattern"
CONF_NOTIFY_OFF_PATTERN = "notify_off_pattern"

ENTITY_TYPE_SWITCH = "switch"
ENTITY_TYPE_BUTTON = "button"
ENTITY_TYPE_SELECT = "select"
ENTITY_TYPES = [ENTITY_TYPE_SWITCH, ENTITY_TYPE_BUTTON, ENTITY_TYPE_SELECT]
