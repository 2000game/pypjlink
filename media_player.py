"""Support for controlling projector via the PJLink protocol."""
from custom_components.custom_pjlink.projector import MUTE_AUDIO, Projector
from custom_components.custom_pjlink.projector import ProjectorError
import voluptuous as vol
from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.helpers.config_validation as cv

import logging

import time

_LOGGER = logging.getLogger(__name__)

CONF_ENCODING = "encoding"

DEFAULT_PORT = 4352
DEFAULT_ENCODING = "utf-8"
DEFAULT_TIMEOUT = 20

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)

SUPPORT_PJLINK = (
    SUPPORT_VOLUME_MUTE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the PJLink platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    encoding = config.get(CONF_ENCODING)
    password = config.get(CONF_PASSWORD)

    if "pjlink" not in hass.data:
        hass.data["pjlink"] = {}
    hass_data = hass.data["pjlink"]

    device_label = f"{host}:{port}"
    if device_label in hass_data:
        return

    device = PjLinkDevice(host, port, name, encoding, password)
    hass_data[device_label] = device
    add_entities([device], True)


def format_input_source(input_source_name, input_source_number):
    """Format input source for display in UI."""
    return f"{input_source_name} {input_source_number}"


class PjLinkDevice(MediaPlayerEntity):
    """Representation of a PJLink device."""

    def __init__(self, host, port, name, encoding, password):
        """Iinitialize the PJLink device."""
        self._host = host
        self._port = port
        self._name = name
        self._password = password
        self._encoding = encoding
        self._muted = False
        self._pwstate = STATE_OFF
        self._current_source = None
        projector = self.projector()
        if projector is None:
            self._source_name_mapping = []
            self._source_list = []
            return

        with projector:
            if not self._name:
                self._name = projector.get_name()
            inputs = projector.get_inputs()

        self._source_name_mapping = {format_input_source(*x): x for x in inputs}
        self._source_list = sorted(self._source_name_mapping.keys())
    
        #if not self._name:
        #    self._name = projector().get_name()
        #inputs = projector().get_inputs()


    def projector(self):
        """Create PJLink Projector instance."""
        #_LOGGER.error("Host:  %s, Port: %s", self._host, self._port)
        try:
            projector = Projector.from_address(
                self._host, self._port
            )
        
            projector.authenticate(self._password)
            return projector

        except ProjectorError as err:
                if str(err) == "projector unreachable":
                    self._pwstate = STATE_OFF
                    self._muted = False
                    self._current_source = None
                elif str(err) == "unavailable time":
                    self._pwstate = STATE_OFF
                    self._muted = False
                    self._current_source = None
                else:
                    raise

    def update(self):
        """Get the latest state from the device."""
        projector = self.projector()

        if projector is None:
            self._pwstate = STATE_OFF
            self._muted = False
            self._current_source = None 
            return

        with projector:
            try:
                pwstate = projector.get_power()
                inputs = projector.get_inputs()
                if pwstate in ("on", "warm-up"):
                    self._pwstate = STATE_ON
                    self._muted = projector.get_mute()[1]
                    self._current_source = format_input_source(*projector.get_input())
                else:
                    self._pwstate = STATE_OFF
                    self._muted = False
                    self._current_source = None
                self._source_name_mapping = {format_input_source(*x): x for x in inputs}
                self._source_list = sorted(self._source_name_mapping.keys())
            except KeyError as err:
                #_LOGGER.error(err)
                if str(err) == "'OK'":
                    self._pwstate = STATE_OFF
                    self._muted = False
                    self._current_source = None
                else:
                    raise
            except ProjectorError as err:
                #_LOGGER.error(err)
                if str(err) == "unavailable time":
                    self._pwstate = STATE_OFF
                    self._muted = False
                    self._current_source = None
                else:
                    raise

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._pwstate

    @property
    def is_volume_muted(self):
        """Return boolean indicating mute status."""
        return self._muted

    @property
    def source(self):
        """Return current input source."""
        return self._current_source

    @property
    def source_list(self):
        """Return all available input sources."""
        return self._source_list

    @property
    def supported_features(self):
        """Return projector supported features."""
        return SUPPORT_PJLINK

    def turn_off(self):
        """Turn projector off."""
        if self.projector() is None:
            return
        with self.projector() as projector:
            try:
                projector.set_power("off")
            except ProjectorError as err:
                if str(err) == "unavailable time":
                    time.sleep(5)
                    if self._pwstate == STATE_ON:
                        projector.set_power("off")
                else:
                    raise

    def turn_on(self):
        """Turn projector on."""
        if self.projector() is None:
            return
        with self.projector() as projector:
            try:
                projector.set_power("on")
            except ProjectorError as err:
                if str(err) == "unavailable time":
                    time.sleep(8)
                    if self._pwstate == STATE_OFF:
                        projector.set_power("on")
                else:
                    raise

    def mute_volume(self, mute):
        if self.projector() is None:
            return
        """Mute (true) of unmute (false) media player."""
        with self.projector() as projector:
            projector.set_mute(MUTE_AUDIO, mute)

    def select_source(self, source):
        """Set the input source."""
        if self.projector() is None:
            return

        source = self._source_name_mapping[source]
        with self.projector() as projector:
            try:
                projector.set_input(*source)
            except ProjectorError as err:
                if str(err) == "unavailable time":
                    if self._pwstate == STATE_OFF:
                        pass
                else:
                    raise