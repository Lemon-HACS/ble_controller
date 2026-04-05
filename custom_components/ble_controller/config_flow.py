"""BLE Controller config flow."""

from __future__ import annotations

import re

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_CHAR_UUID,
    CONF_DATA_OFF,
    CONF_DATA_ON,
    CONF_DATA_PRESS,
    CONF_ENTITY_TYPE,
    CONF_KEEP_ALIVE,
    CONF_STATUS_QUERY_DATA,
    CONF_NOTIFY_OFF_PATTERN,
    CONF_NOTIFY_ON_PATTERN,
    CONF_NOTIFY_UUID,
    CONF_OPTIONS,
    CONF_SERVICE_UUID,
    CONF_WRITE_WITH_RESPONSE,
    DOMAIN,
    ENTITY_TYPE_BUTTON,
    ENTITY_TYPE_SELECT,
    ENTITY_TYPE_SWITCH,
)

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


def _uuid(value: str) -> str:
    value = value.strip().lower()
    if not UUID_RE.match(value):
        raise vol.Invalid("UUID 형식이 아닙니다")
    return value


def _hex(value: str) -> str:
    value = value.strip().replace(" ", "").lower()
    if not value:
        raise vol.Invalid("빈 값입니다")
    if not HEX_RE.match(value):
        raise vol.Invalid("hex 형식이 아닙니다")
    if len(value) % 2 != 0:
        raise vol.Invalid("hex는 짝수 자리여야 합니다")
    return value


def _parse_select_options(raw: str) -> list[dict[str, str]]:
    """'라벨=hex' 형식의 줄바꿈 구분 문자열을 파싱.

    예시:
        냉방=0aa50201
        난방=0aa50202
        제습=0aa50203
    """
    options = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if "=" not in line:
            raise vol.Invalid(f"'라벨=hex데이터' 형식이 아닙니다: {line}")
        label, data = line.split("=", 1)
        label = label.strip()
        data = _hex(data)
        if not label:
            raise vol.Invalid("라벨이 비어있습니다")
        options.append({"label": label, "data": data})
    if not options:
        raise vol.Invalid("최소 1개 이상의 옵션이 필요합니다")
    return options


class BLEControllerConfigFlow(ConfigFlow, domain=DOMAIN):
    """BLE Controller config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._address: str | None = None
        self._device_name: str | None = None
        self._base_data: dict = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BLEControllerOptionsFlow()

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """1단계: BLE 디바이스 선택."""
        if user_input is not None:
            addr = user_input[CONF_ADDRESS]
            info = self._devices.get(addr)
            self._address = addr
            self._device_name = info.name if info else addr
            return await self.async_step_type()

        discovered = async_discovered_service_info(self.hass, connectable=True)
        self._devices = {}
        for info in discovered:
            if info.address not in self._devices:
                self._devices[info.address] = info

        if not self._devices:
            return self.async_abort(reason="no_devices_found")

        labels = {
            addr: f"{info.name or 'Unknown'} ({addr})"
            for addr, info in self._devices.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(labels)}),
        )

    async def async_step_type(self, user_input: dict | None = None) -> FlowResult:
        """2단계: 엔티티 타입 선택."""
        if user_input is not None:
            entity_type = user_input[CONF_ENTITY_TYPE]
            if entity_type == ENTITY_TYPE_SWITCH:
                return await self.async_step_switch()
            if entity_type == ENTITY_TYPE_BUTTON:
                return await self.async_step_button()
            return await self.async_step_select()

        type_labels = {
            ENTITY_TYPE_SWITCH: "스위치 (ON/OFF)",
            ENTITY_TYPE_BUTTON: "버튼 (단발성 커맨드)",
            ENTITY_TYPE_SELECT: "셀렉트 (다중 선택)",
        }
        return self.async_show_form(
            step_id="type",
            data_schema=vol.Schema(
                {vol.Required(CONF_ENTITY_TYPE): vol.In(type_labels)}
            ),
        )

    async def async_step_switch(self, user_input: dict | None = None) -> FlowResult:
        """스위치 설정: UUID + ON/OFF 데이터."""
        errors = {}
        if user_input is not None:
            try:
                service_uuid = _uuid(user_input[CONF_SERVICE_UUID])
                char_uuid = _uuid(user_input[CONF_CHAR_UUID])
                data_on = _hex(user_input[CONF_DATA_ON])
                data_off = _hex(user_input[CONF_DATA_OFF])
            except vol.Invalid:
                errors["base"] = "invalid_format"
            else:
                self._base_data = {
                    CONF_ADDRESS: self._address,
                    CONF_NAME: self._device_name,
                    CONF_ENTITY_TYPE: ENTITY_TYPE_SWITCH,
                    CONF_SERVICE_UUID: service_uuid,
                    CONF_CHAR_UUID: char_uuid,
                    CONF_DATA_ON: data_on,
                    CONF_DATA_OFF: data_off,
                    CONF_WRITE_WITH_RESPONSE: user_input.get(
                        CONF_WRITE_WITH_RESPONSE, False
                    ),
                    CONF_KEEP_ALIVE: user_input.get(CONF_KEEP_ALIVE, False),
                }
                return await self.async_step_notify()

        return self.async_show_form(
            step_id="switch",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERVICE_UUID): str,
                    vol.Required(CONF_CHAR_UUID): str,
                    vol.Required(CONF_DATA_ON): str,
                    vol.Required(CONF_DATA_OFF): str,
                    vol.Optional(CONF_WRITE_WITH_RESPONSE, default=False): bool,
                    vol.Optional(CONF_KEEP_ALIVE, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_button(self, user_input: dict | None = None) -> FlowResult:
        """버튼 설정: UUID + 커맨드 데이터."""
        errors = {}
        if user_input is not None:
            try:
                service_uuid = _uuid(user_input[CONF_SERVICE_UUID])
                char_uuid = _uuid(user_input[CONF_CHAR_UUID])
                data_press = _hex(user_input[CONF_DATA_PRESS])
            except vol.Invalid:
                errors["base"] = "invalid_format"
            else:
                await self.async_set_unique_id(
                    f"{self._address}_{char_uuid}_button"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self._device_name or "BLE Button",
                    data={
                        CONF_ADDRESS: self._address,
                        CONF_NAME: self._device_name,
                        CONF_ENTITY_TYPE: ENTITY_TYPE_BUTTON,
                        CONF_SERVICE_UUID: service_uuid,
                        CONF_CHAR_UUID: char_uuid,
                        CONF_DATA_PRESS: data_press,
                        CONF_WRITE_WITH_RESPONSE: user_input.get(
                            CONF_WRITE_WITH_RESPONSE, False
                        ),
                        CONF_KEEP_ALIVE: user_input.get(CONF_KEEP_ALIVE, False),
                    },
                )

        return self.async_show_form(
            step_id="button",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERVICE_UUID): str,
                    vol.Required(CONF_CHAR_UUID): str,
                    vol.Required(CONF_DATA_PRESS): str,
                    vol.Optional(CONF_WRITE_WITH_RESPONSE, default=False): bool,
                    vol.Optional(CONF_KEEP_ALIVE, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_select(self, user_input: dict | None = None) -> FlowResult:
        """셀렉트 설정: UUID + 옵션 목록."""
        errors = {}
        if user_input is not None:
            try:
                service_uuid = _uuid(user_input[CONF_SERVICE_UUID])
                char_uuid = _uuid(user_input[CONF_CHAR_UUID])
                options = _parse_select_options(user_input[CONF_OPTIONS])
            except vol.Invalid:
                errors["base"] = "invalid_format"
            else:
                await self.async_set_unique_id(
                    f"{self._address}_{char_uuid}_select"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self._device_name or "BLE Select",
                    data={
                        CONF_ADDRESS: self._address,
                        CONF_NAME: self._device_name,
                        CONF_ENTITY_TYPE: ENTITY_TYPE_SELECT,
                        CONF_SERVICE_UUID: service_uuid,
                        CONF_CHAR_UUID: char_uuid,
                        CONF_OPTIONS: options,
                        CONF_WRITE_WITH_RESPONSE: user_input.get(
                            CONF_WRITE_WITH_RESPONSE, False
                        ),
                        CONF_KEEP_ALIVE: user_input.get(CONF_KEEP_ALIVE, False),
                    },
                )

        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERVICE_UUID): str,
                    vol.Required(CONF_CHAR_UUID): str,
                    vol.Required(CONF_OPTIONS): str,
                    vol.Optional(CONF_WRITE_WITH_RESPONSE, default=False): bool,
                    vol.Optional(CONF_KEEP_ALIVE, default=False): bool,
                }
            ),
            errors=errors,
            description_placeholders={
                "options_format": "라벨=hex데이터 (줄바꿈 구분)"
            },
        )

    async def async_step_notify(self, user_input: dict | None = None) -> FlowResult:
        """스위치 전용: Notify 설정 (선택)."""
        if user_input is not None:
            data = self._base_data
            errors = {}

            notify_uuid = user_input.get(CONF_NOTIFY_UUID, "").strip()
            notify_on = user_input.get(CONF_NOTIFY_ON_PATTERN, "").strip()
            notify_off = user_input.get(CONF_NOTIFY_OFF_PATTERN, "").strip()

            status_query = user_input.get(CONF_STATUS_QUERY_DATA, "").strip()

            try:
                if notify_uuid:
                    data[CONF_NOTIFY_UUID] = _uuid(notify_uuid)
                    if notify_on:
                        data[CONF_NOTIFY_ON_PATTERN] = _hex(notify_on)
                    if notify_off:
                        data[CONF_NOTIFY_OFF_PATTERN] = _hex(notify_off)
                    if status_query:
                        data[CONF_STATUS_QUERY_DATA] = _hex(status_query)
            except vol.Invalid:
                errors["base"] = "invalid_format"
                return self.async_show_form(
                    step_id="notify",
                    data_schema=self._notify_schema(),
                    errors=errors,
                )

            await self.async_set_unique_id(
                f"{self._address}_{data[CONF_CHAR_UUID]}_switch"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._device_name or "BLE Switch",
                data=data,
            )

        return self.async_show_form(
            step_id="notify",
            data_schema=self._notify_schema(),
        )

    @staticmethod
    def _notify_schema() -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(CONF_NOTIFY_UUID, default=""): str,
                vol.Optional(CONF_NOTIFY_ON_PATTERN, default=""): str,
                vol.Optional(CONF_NOTIFY_OFF_PATTERN, default=""): str,
                vol.Optional(CONF_STATUS_QUERY_DATA, default=""): str,
            }
        )


class BLEControllerOptionsFlow(OptionsFlow):
    """BLE Controller 옵션 플로우."""

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        entity_type = self.config_entry.data.get(CONF_ENTITY_TYPE, ENTITY_TYPE_SWITCH)

        if entity_type == ENTITY_TYPE_SWITCH:
            return await self.async_step_switch_options(user_input)
        if entity_type == ENTITY_TYPE_BUTTON:
            return await self.async_step_button_options(user_input)
        return await self.async_step_select_options(user_input)

    async def async_step_switch_options(
        self, user_input: dict | None = None
    ) -> FlowResult:
        errors = {}
        data = self.config_entry.data

        if user_input is not None:
            try:
                new = {**data}
                new[CONF_DATA_ON] = _hex(user_input[CONF_DATA_ON])
                new[CONF_DATA_OFF] = _hex(user_input[CONF_DATA_OFF])
                new[CONF_WRITE_WITH_RESPONSE] = user_input.get(
                    CONF_WRITE_WITH_RESPONSE, False
                )
                new[CONF_KEEP_ALIVE] = user_input.get(CONF_KEEP_ALIVE, False)
                notify_uuid = user_input.get(CONF_NOTIFY_UUID, "").strip()
                status_query = user_input.get(CONF_STATUS_QUERY_DATA, "").strip()
                if notify_uuid:
                    new[CONF_NOTIFY_UUID] = _uuid(notify_uuid)
                    on_p = user_input.get(CONF_NOTIFY_ON_PATTERN, "").strip()
                    off_p = user_input.get(CONF_NOTIFY_OFF_PATTERN, "").strip()
                    if on_p:
                        new[CONF_NOTIFY_ON_PATTERN] = _hex(on_p)
                    if off_p:
                        new[CONF_NOTIFY_OFF_PATTERN] = _hex(off_p)
                    if status_query:
                        new[CONF_STATUS_QUERY_DATA] = _hex(status_query)
                    else:
                        new.pop(CONF_STATUS_QUERY_DATA, None)
                else:
                    new.pop(CONF_NOTIFY_UUID, None)
                    new.pop(CONF_NOTIFY_ON_PATTERN, None)
                    new.pop(CONF_NOTIFY_OFF_PATTERN, None)
                    new.pop(CONF_STATUS_QUERY_DATA, None)
            except vol.Invalid:
                errors["base"] = "invalid_format"
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="switch_options",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DATA_ON, default=data.get(CONF_DATA_ON, "")): str,
                    vol.Required(CONF_DATA_OFF, default=data.get(CONF_DATA_OFF, "")): str,
                    vol.Optional(
                        CONF_WRITE_WITH_RESPONSE,
                        default=data.get(CONF_WRITE_WITH_RESPONSE, False),
                    ): bool,
                    vol.Optional(
                        CONF_KEEP_ALIVE,
                        default=data.get(CONF_KEEP_ALIVE, False),
                    ): bool,
                    vol.Optional(
                        CONF_NOTIFY_UUID, default=data.get(CONF_NOTIFY_UUID, "")
                    ): str,
                    vol.Optional(
                        CONF_NOTIFY_ON_PATTERN,
                        default=data.get(CONF_NOTIFY_ON_PATTERN, ""),
                    ): str,
                    vol.Optional(
                        CONF_NOTIFY_OFF_PATTERN,
                        default=data.get(CONF_NOTIFY_OFF_PATTERN, ""),
                    ): str,
                    vol.Optional(
                        CONF_STATUS_QUERY_DATA,
                        default=data.get(CONF_STATUS_QUERY_DATA, ""),
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_button_options(
        self, user_input: dict | None = None
    ) -> FlowResult:
        errors = {}
        data = self.config_entry.data

        if user_input is not None:
            try:
                new = {**data}
                new[CONF_DATA_PRESS] = _hex(user_input[CONF_DATA_PRESS])
                new[CONF_WRITE_WITH_RESPONSE] = user_input.get(
                    CONF_WRITE_WITH_RESPONSE, False
                )
                new[CONF_KEEP_ALIVE] = user_input.get(CONF_KEEP_ALIVE, False)
            except vol.Invalid:
                errors["base"] = "invalid_format"
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="button_options",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DATA_PRESS, default=data.get(CONF_DATA_PRESS, "")
                    ): str,
                    vol.Optional(
                        CONF_WRITE_WITH_RESPONSE,
                        default=data.get(CONF_WRITE_WITH_RESPONSE, False),
                    ): bool,
                    vol.Optional(
                        CONF_KEEP_ALIVE,
                        default=data.get(CONF_KEEP_ALIVE, False),
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_select_options(
        self, user_input: dict | None = None
    ) -> FlowResult:
        errors = {}
        data = self.config_entry.data

        if user_input is not None:
            try:
                options = _parse_select_options(user_input[CONF_OPTIONS])
                new = {**data}
                new[CONF_OPTIONS] = options
                new[CONF_WRITE_WITH_RESPONSE] = user_input.get(
                    CONF_WRITE_WITH_RESPONSE, False
                )
                new[CONF_KEEP_ALIVE] = user_input.get(CONF_KEEP_ALIVE, False)
            except vol.Invalid:
                errors["base"] = "invalid_format"
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new
                )
                return self.async_create_entry(title="", data={})

        current_options = data.get(CONF_OPTIONS, [])
        current_text = "\n".join(
            f"{opt['label']}={opt['data']}" for opt in current_options
        )

        return self.async_show_form(
            step_id="select_options",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OPTIONS, default=current_text): str,
                    vol.Optional(
                        CONF_WRITE_WITH_RESPONSE,
                        default=data.get(CONF_WRITE_WITH_RESPONSE, False),
                    ): bool,
                    vol.Optional(
                        CONF_KEEP_ALIVE,
                        default=data.get(CONF_KEEP_ALIVE, False),
                    ): bool,
                }
            ),
            errors=errors,
        )
