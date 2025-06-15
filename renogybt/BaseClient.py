import asyncio
import logging
import traceback
from .BLEManager import BLEManager
from .Utils import bytes_to_int, crc16_modbus, int_to_bytes
from .ConfigManager import ConfigManager
from .exceptions import DeviceNotFoundError, ConnectionError, ReadTimeoutError, InvalidResponseError
from . import constants as C # Import constants

# Base class that works with all Renogy family devices
# Should be extended by each client with its own parsers and section definitions
# Section example: {C.KEY_REGISTER: 5000, C.KEY_WORDS: 8, C.KEY_PARSER: self.parser_func}

logger = logging.getLogger(__name__) # Module-level logger for BaseClient

class BaseClient:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.ble_manager = None
        self.device = None # This will store the bleak device object
        self.poll_timer = None
        self.read_timeout = None
        self.data = self._get_empty_data_container() # Initialize with potentially a dataclass

        # Device identification from config
        self.device_mac_address = self.config_manager.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_MAC_ADDR)
        self.device_alias = self.config_manager.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_ALIAS)
        self.device_id_from_config = int(self.config_manager.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_DEVICE_ID)) # Renamed for clarity

        # Connection retry settings
        self.connect_retries = int(self.config_manager.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_CONNECT_RETRIES, fallback='3'))
        self.connect_retry_delay = int(self.config_manager.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_CONNECT_RETRY_DELAY, fallback='5'))

        self.sections = [] # To be defined by child classes
        self.section_index = 0
        self.loop = None
        logger.info(f"Initializing {self.__class__.__name__} for {self.device_alias} ({self.device_mac_address})")

    def start(self):
        logger.info(f"Starting client for {self.device_alias}...")
        try:
            self.loop = asyncio.get_event_loop()
            self.loop.create_task(self._managed_connect())
            self.future = self.loop.create_future()
            self.loop.run_until_complete(self.future)
        except RenogyBTError as e:
            # Error already logged by __on_error, this is for program control flow
            logger.debug(f"RenogyBTError caught in start(): {e}")
        except Exception as e:
            logger.error(f"Unexpected exception in start(): {e}", exc_info=True)
            self.__on_error(e) # Ensure it's processed by our handler
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received in start(), stopping.")
            self.loop = None # Ensure loop is None so stop() creates a new one if needed
            self.__on_error("KeyboardInterrupt")
        logger.info(f"Client for {self.device_alias} stopped.")


    async def _managed_connect(self):
        """Manages connection attempts including retries."""
        attempts = 0
        logger.info(f"Attempting to connect to {self.device_alias} ({self.device_mac_address})...")
        while attempts <= self.connect_retries:
            try:
                await self.connect()
                logger.info(f"Successfully connected to {self.device_alias} after {attempts + 1} attempt(s).")
                return
            except DeviceNotFoundError as e:
                logger.error(f"Attempt {attempts + 1}: Device {self.device_alias} not found. {e}")
                self.__on_error(e)
                return
            except ConnectionError as e:
                logger.warning(f"Attempt {attempts + 1} to connect to {self.device_alias} failed: {e}")
                attempts += 1
                if attempts <= self.connect_retries:
                    logger.info(f"Retrying connection to {self.device_alias} in {self.connect_retry_delay} seconds... ({attempts}/{self.connect_retries})")
                    await asyncio.sleep(self.connect_retry_delay)
                else:
                    logger.error(f"Max connection retries ({self.connect_retries}) reached for {self.device_alias}.")
                    self.__on_error(e)
                    return
            except Exception as e:
                logger.error(f"An unexpected error occurred during connection attempt {attempts + 1} for {self.device_alias}: {e}", exc_info=True)
                self.__on_error(e)
                return

    async def connect(self):
        """Establishes connection to the BLE device."""
        logger.debug(f"Initializing BLEManager for {self.device_alias} ({self.device_mac_address})")
        self.ble_manager = BLEManager(
            mac_address=self.device_mac_address, # Use already fetched value
            alias=self.device_alias, # Use already fetched value
            on_data=self.on_data_received,
            on_connect_fail=self._on_ble_connect_fail,
            notify_char_uuid=C.UUID_NOTIFY_CHAR,
            write_char_uuid=C.UUID_WRITE_CHAR,
            write_service_uuid=C.UUID_WRITE_SERVICE
        )

        logger.debug(f"Starting device discovery for {self.device_alias}...")
        try:
            await self.ble_manager.discover()
            self.device = self.ble_manager.device # Store the bleak device object
        except Exception as e:
            raise ConnectionError(f"Discovery failed for {self.device_alias}: {e}")

        if not self.device:
            error_msg = f"Device {self.device_alias} ({self.device_mac_address}) not found after discovery."
            possible_devices = [f"{dev.name} > [{dev.address}]" for dev in self.ble_manager.discovered_devices if dev.name and dev.name.startswith(tuple(C.DEVICE_ALIAS_PREFIXES))]
            if possible_devices:
                error_msg += " Possible devices found: " + ", ".join(possible_devices)
            logger.warning(error_msg)
            raise DeviceNotFoundError(error_msg)

        logger.debug(f"Device {self.device_alias} found, attempting to connect...")
        try:
            await self.ble_manager.connect()
        except Exception as e:
            raise ConnectionError(f"Connection to {self.device.address} ({self.device_alias}) failed: {e}")

        if self.ble_manager.client and self.ble_manager.client.is_connected:
            logger.info(f"Successfully connected to BLE device: {self.device.address} ({self.device_alias})")
            await self.read_section() # Start reading data
        else:
            msg = f"Failed to connect to {self.device.address} ({self.device_alias}), client not connected."
            logger.error(msg)
            raise ConnectionError(msg)


    async def disconnect(self):
        logger.info(f"Disconnecting from {self.device_alias or self.device_mac_address}...")
        if self.ble_manager:
            await self.ble_manager.disconnect()
        logger.info(f"Disconnected from {self.device_alias or self.device_mac_address}.")
        if self.future and not self.future.done():
            self.future.set_result('DONE')


    async def on_data_received(self, response):
        logger.debug(f"Raw data received: {response.hex()}")
        if self.read_timeout and not self.read_timeout.cancelled():
            logger.debug("Cancelling read timeout.")
            self.read_timeout.cancel()

        operation = bytes_to_int(response, 1, 1)
        logger.debug(f"Parsed operation code: {operation}")

        if operation == C.OP_CODE_READ_SUCCESS or operation == C.OP_CODE_READ_ERROR:
            current_section_def = self.sections[self.section_index]
            expected_len = current_section_def[C.KEY_WORDS] * 2 + 5

            if operation == C.OP_CODE_READ_SUCCESS and \
               self.section_index < len(self.sections) and \
               current_section_def[C.KEY_PARSER] is not None and \
               expected_len == len(response):
                logger.info(f"Read operation successful for section {self.section_index} (Register: {current_section_def[C.KEY_REGISTER]}). Parsing data...")
                self.__safe_parser(current_section_def[C.KEY_PARSER], response)
            elif operation == C.OP_CODE_READ_ERROR:
                 logger.error(f"Device returned a read error for section {self.section_index} (Register: {current_section_def[C.KEY_REGISTER]}): {response.hex()}")
                 # Decide if we should stop or raise InvalidResponseError
            elif not (expected_len == len(response)):
                msg = f"Invalid response length for section {self.section_index} (Register: {current_section_def[C.KEY_REGISTER]}): expected {expected_len}, got {len(response)}. Response: {response.hex()}"
                logger.error(msg)
                raise InvalidResponseError(msg)
            else: # Should not happen if conditions above are exhaustive for success/error
                logger.warning(f"Read operation for section {self.section_index} (Register: {current_section_def[C.KEY_REGISTER]}) failed or unexpected response: {response.hex()}")

            if self.section_index >= len(self.sections) - 1:
                logger.info("All sections read successfully. Read cycle complete.")
                self.section_index = 0
                self.on_read_operation_complete()
                self.data = self._get_empty_data_container()
                await self.check_polling()
            else:
                self.section_index += 1
                logger.debug(f"Moving to next section {self.section_index}. Waiting a bit before next read.")
                await asyncio.sleep(0.5) # Consider making this delay configurable
                await self.read_section()
        else:
            logger.warning(f"Unknown operation code {operation} received: {response.hex()}")

    def on_read_operation_complete(self):
        logger.info(f"All sections parsed for {self.device_alias}. Preparing data for callback.")

        # Add metadata (__device, __client) to the data object before callback
        # This needs to work for both dicts and dataclass instances
        device_alias_val = self.config_manager.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_ALIAS)
        client_name_val = self.__class__.__name__

        if isinstance(self.data, dict):
            self.data[C.META_DEVICE_ALIAS] = device_alias_val
            self.data[C.META_CLIENT_NAME] = client_name_val
        else:
            try:
                setattr(self.data, C.META_DEVICE_ALIAS, device_alias_val)
                setattr(self.data, C.META_CLIENT_NAME, client_name_val)
            except Exception as e:
                logger.warning(f"Could not set metadata on data object of type {type(self.data)}: {e}", exc_info=True)

        logger.debug(f"Data for callback: {self.data}")
        self.__safe_callback(self.on_data_callback, self.data)

    def on_read_timeout(self):
        error_msg = f"Read operation timed out for device ID {self.device_id_from_config} on section {self.section_index} (Register: {self.sections[self.section_index].get(C.KEY_REGISTER, 'N/A')})"
        logger.error(error_msg)
        self.__on_error(ReadTimeoutError(error_msg))

    async def check_polling(self):
        if self.config_manager.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_ENABLE_POLLING).lower() == 'true':
            poll_interval_s = int(self.config_manager.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_POLL_INTERVAL))
            logger.info(f"Polling enabled. Waiting {poll_interval_s}s for next read cycle for {self.device_alias}.")
            await asyncio.sleep(poll_interval_s)
            logger.debug(f"Polling interval ended for {self.device_alias}. Starting new read section.")
            await self.read_section()
        else:
            logger.info(f"Polling disabled for {self.device_alias}. Client will stop after current operations.")
            # If not polling, and all sections are read, the client effectively stops data acquisition part.
            # The main loop in start() will continue until future is set (e.g. by disconnect or error).
            # If auto-stop is desired after one read when polling is off:
            # self.stop() # or self.loop.create_task(self.disconnect())

    async def read_section(self):
        index = self.section_index
        if self.device_id_from_config is None or len(self.sections) == 0: # Check renamed device_id
            logger.error(f"{self.__class__.__name__} cannot be used directly or device_id is not set.")
            return

        current_section_def = self.sections[index]
        register_to_read = current_section_def[C.KEY_REGISTER]
        words_to_read = current_section_def[C.KEY_WORDS]
        logger.info(f"Reading section {index} for {self.device_alias}: Register {register_to_read}, Words {words_to_read}")

        self.read_timeout = self.loop.call_later(C.DEFAULT_READ_TIMEOUT_S, self.on_read_timeout)
        request = self.create_generic_read_request(
            self.device_id_from_config,
            C.OP_CODE_READ,
            register_to_read,
            words_to_read
        )
        logger.debug(f"Sending read request for section {index} (Register: {register_to_read}): {request}")
        await self.ble_manager.characteristic_write_value(request)

    def create_generic_read_request(self, device_id, function_code, register_addr, read_word_count):
        payload = [] # Initialize to empty list
        if register_addr is not None and read_word_count is not None:
            payload.append(device_id)
            payload.append(function_code)
            payload.append(int_to_bytes(register_addr, 0))
            payload.append(int_to_bytes(register_addr, 1))
            payload.append(int_to_bytes(read_word_count, 0))
            payload.append(int_to_bytes(read_word_count, 1))

            crc = crc16_modbus(bytes(payload))
            payload.append(crc[0])
            payload.append(crc[1])
            logger.debug(f"Created read request payload for device {device_id}, register {register_addr}: {payload}")
        else:
            logger.warning("Cannot create read request: register_addr or read_word_count is None.")
            return None # Explicitly return None if parameters are missing
        return payload

    def __on_error(self, error = None):
        error_msg = f"Error in {self.__class__.__name__} for {self.device_alias}: {error.__class__.__name__ if isinstance(error, Exception) else 'Unknown Error'}: {error}"
        logger.error(error_msg, exc_info=isinstance(error, Exception)) # Add stack trace for exceptions

        self.__safe_callback(self.on_error_callback, error)

        if self.future and not self.future.done():
            if isinstance(error, Exception):
                self.future.set_exception(error)
            else: # Wrap string errors, though we try to use Exception objects now
                self.future.set_exception(RenogyBTError(str(error)))

        if self.ble_manager: # Attempt graceful disconnect
             if self.loop and not self.loop.is_closed():
                logger.debug("Scheduling BLE disconnect via loop due to error.")
                self.loop.create_task(self.ble_manager.disconnect())
             elif self.ble_manager.client and self.ble_manager.client.is_connected:
                 logger.debug("Running BLE disconnect synchronously due to error (no loop or loop closed).")
                 asyncio.run(self.ble_manager.disconnect())


    def _on_ble_connect_fail(self, error_message: str):
        """Internal handler for BLEManager's on_connect_fail."""
        logger.warning(f"BLE connection failed for {self.device_alias}: {error_message}. This will be handled by the retry logic in _managed_connect.")
        # No direct call to __on_error here, let _managed_connect handle it to allow retries.

    def stop(self):
        logger.info(f"Stop called for client {self.device_alias}. Cleaning up...")
        if self.read_timeout and not self.read_timeout.cancelled():
            logger.debug("Cancelling active read timeout.")
            self.read_timeout.cancel()

        # Disconnect if connected or attempting connection
        if self.ble_manager:
            if self.loop and self.loop.is_running() and not self.loop.is_closed():
                logger.debug("Scheduling disconnect task in existing loop.")
                self.loop.create_task(self.disconnect())
            else: # Fallback if loop isn't usable
                try:
                    logger.debug("Attempting synchronous disconnect as loop is not available/running.")
                    asyncio.run(self.disconnect())
                except RuntimeError as e: # e.g. if another loop is already running
                    logger.error(f"Error during synchronous disconnect for {self.device_alias}: {e}", exc_info=True)
        elif self.future and not self.future.done(): # If ble_manager not even init'd but future exists
             self.future.set_result('STOPPED_PRE_CONNECT')


        # If the main future hasn't been resolved, resolve it.
        if self.future and not self.future.done():
            logger.debug("Setting main future result to 'DONE' as part of stop sequence.")
            self.future.set_result('DONE') # Or appropriate status
        logger.info(f"Client stop sequence for {self.device_alias} completed.")


    def __safe_callback(self, calback, param):
        if calback is not None:
            try:
                logger.debug(f"Executing callback {calback.__name__} with param: {param}")
                calback(self, param)
            except Exception as e:
                logger.error(f"Exception in callback {calback.__name__}: {e}", exc_info=True)
                # Do not call __on_error from here to avoid potential loops if callback itself causes error.

    def __safe_parser(self, parser, param):
        if not self.data:
            self.data = self._get_empty_data_container()
            logger.debug("Re-initialized self.data in __safe_parser as it was empty.")

        if parser is not None:
            try:
                logger.debug(f"Executing parser {parser.__name__}...")
                parser(param)
                logger.debug(f"Parser {parser.__name__} executed successfully.")
            except Exception as e:
                logger.error(f"Exception in parser {parser.__name__}: {e}", exc_info=True)
                self.__on_error(InvalidResponseError(f"Error parsing data with {parser.__name__}: {e}"))

    # Generic parsing methods
    def _parse_device_info(self, response_bytes, model_start_index, model_end_index, strip_chars=None):
        if not self.data: self.data = self._get_empty_data_container() # Should ideally be set
        logger.debug(f"Parsing device info (model) from response.")
        raw_model = response_bytes[model_start_index:model_end_index]
        model_str = "Unknown"
        try:
            model_str = raw_model.decode('utf-8')
            if strip_chars:
                model_str = model_str.strip(strip_chars)
            else:
                model_str = model_str.strip()
            logger.debug(f"Parsed model: {model_str}")
        except UnicodeDecodeError:
            logger.warning(f"Could not decode model string from raw: {raw_model.hex()}")

        if hasattr(self.data, C.KEY_MODEL):
            self.data.model = model_str
        else:
            logger.warning(f"_parse_device_info: self.data (type: {type(self.data)}) has no '{C.KEY_MODEL}' attribute.")


    def _parse_device_address(self, response_bytes, address_start_index, address_length_bytes):
        if not self.data: self.data = self._get_empty_data_container() # Should ideally be set
        logger.debug(f"Parsing device address (ID) from response.")
        device_id_from_device = bytes_to_int(response_bytes, address_start_index, address_length_bytes)
        logger.debug(f"Parsed device ID from device: {device_id_from_device}")

        if hasattr(self.data, C.KEY_DEVICE_ID):
            self.data.device_id = device_id_from_device
        else:
            logger.warning(f"_parse_device_address: self.data (type: {type(self.data)}) has no '{C.KEY_DEVICE_ID}' attribute.")

        # Optional: Log mismatch if device_id from device differs from config (already in some clients)

        if self.device_id_from_config != device_id_from_device:
            logger.warning(f"Device ID mismatch: Configured ID {self.device_id_from_config}, ID from device {device_id_from_device}.")

    def _get_empty_data_container(self):
        logger.debug("BaseClient._get_empty_data_container() called, returning dict.")
        return {}
