# -*- coding: utf-8 -*-
"""
renogybt.BaseClient
~~~~~~~~~~~~~~~~~~~

This module defines the `BaseClient` class, which serves as the foundation for
all device-specific client implementations in the Renogy BT/BLE library.

The `BaseClient` handles common tasks such as:
- Managing the asyncio event loop and BLE connection lifecycle (connect, disconnect, retries).
- Storing device configuration and BLE manager instances.
- Orchestrating data polling by iterating through a list of data sections
  defined by subclasses.
- Providing common parsing methods for basic device information (model, device ID).
- Handling responses, timeouts, and errors during communication.
- Invoking user-defined callbacks for data reception and errors.

Subclasses are expected to:
- Define the `sections` attribute, which is a list of dictionaries, each
  specifying a data segment to read (register, number of words) and the
  parser method for that segment.
- Implement specific parser methods to interpret the byte responses from the device
  and populate a data container (typically a dataclass instance).
- Override `_get_empty_data_container()` to return an instance of their specific
  data dataclass.
"""
import asyncio
import logging
from typing import Optional, Callable, Any, List, Dict # Added typing imports
from bleak.backends.device import BLEDevice # Import BLEDevice
from .BLEManager import BLEManager
from .Utils import bytes_to_int, crc16_modbus, int_to_bytes
from .ConfigManager import ConfigManager
from .exceptions import (
    DeviceNotFoundError,
    ConnectionError,
    ReadTimeoutError,
    InvalidResponseError,
    RenogyBTError,
)
from . import constants as C

logger = logging.getLogger(__name__)


class BaseClient:
    """
    Base class for Renogy Bluetooth device clients.

    Manages BLE connection, data polling schedules, response parsing,
    and error handling. Designed to be subclassed by specific device clients.

    Args:
        config_manager (ConfigManager): Configuration manager instance.
        on_data_callback (Callable, optional): Async callback for received data.
        on_error_callback (Callable, optional): Callback for errors.
    """

    def __init__(self, config_manager: ConfigManager):
        self.config_manager: ConfigManager = config_manager
        self.ble_manager: Optional[BLEManager] = None
        self.device: Optional[BLEDevice] = (
            None  # bleak.backends.device.BLEDevice
        )
        self.poll_timer: Optional[asyncio.TimerHandle] = None
        self.read_timeout: Optional[asyncio.TimerHandle] = None

        # Device identification from config - initialize these first as they might be used by _get_empty_data_container logging
        self.device_mac_address: str = self.config_manager.get(
            C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_MAC_ADDR
        )
        self.device_alias: str = self.config_manager.get(
            C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_ALIAS
        )
        self.device_id_from_config: int = int( # Ensure this is int
            self.config_manager.get(C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_DEVICE_ID)
        )

        self.data: Any = ( # Changed from 'any' to 'Any' for proper type hint
            self._get_empty_data_container()
        )  # Holds data, typically a dataclass instance


        # Connection retry settings
        self.connect_retries: int = int(
            self.config_manager.get(
                C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_CONNECT_RETRIES, fallback="3"
            )
        )
        self.connect_retry_delay: int = int(
            self.config_manager.get(
                C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_CONNECT_RETRY_DELAY, fallback="5"
            )
        )

        self.sections: List[Dict[str, Any]] = []  # To be defined by child classes
        self.section_index: int = 0
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.future: Optional[asyncio.Future] = None # For main run_until_complete

        # Callbacks - to be set by specific client implementations if needed,
        # or passed to __init__ by the user of the client.
        self.on_data_callback: Optional[Callable[[BaseClient, Any], None]] = None
        self.on_error_callback: Optional[Callable[[BaseClient, Exception], None]] = None


        logger.info(
            f"Initializing {self.__class__.__name__} for device '{self.device_alias}' ({self.device_mac_address})"
        )

    def start(self) -> None:
        """
        Starts the client's operation.

        Initializes the asyncio event loop and runs the main connection and
        data polling logic (_managed_connect) until it completes or an
        unhandled exception occurs.
        """
        logger.info(f"Starting client for '{self.device_alias}'...")
        try:
            self.loop = asyncio.get_event_loop()
            self.future = self.loop.create_future()
            self.loop.create_task(self._managed_connect())
            self.loop.run_until_complete(self.future)
        except RenogyBTError as e:
            logger.debug(f"RenogyBTError caught in start() for '{self.device_alias}': {e}")
        except KeyboardInterrupt:
            logger.info(f"KeyboardInterrupt received in start() for '{self.device_alias}', stopping.")
            # self.loop might be None if KeyboardInterrupt happens very early.
            if self.loop:
                 self.loop.call_soon_threadsafe(self.future.cancel) # Request cancellation
                 # self.loop.run_until_complete(self.future) # Allow cleanup
            self.__on_error(KeyboardInterrupt("User interrupted client start."))
        except Exception as e:
            logger.error(f"Unexpected exception in start() for '{self.device_alias}': {e}", exc_info=True)
            self.__on_error(e)
        finally:
            if self.loop and self.loop.is_running():
                 logger.debug(f"Shutting down asyncio loop for {self.device_alias}...")
                 # self.loop.run_until_complete(self.loop.shutdown_asyncgens()) # Python 3.6+
                 # self.loop.close() # Close loop only if it's the one we started and own.
            logger.info(f"Client for '{self.device_alias}' has stopped.")


    async def _managed_connect(self) -> None:
        """
        Manages the connection process, including discovery and retries.

        This method attempts to connect to the device. If connection fails,
        it retries according to `connect_retries` and `connect_retry_delay`
        settings. Device discovery errors are fatal and do not retry.
        Sets the result or exception on `self.future` upon completion or failure.
        """
        attempts = 0
        logger.info(
            f"Attempting to connect to '{self.device_alias}' ({self.device_mac_address})..."
        )
        try:
            while attempts <= self.connect_retries:
                try:
                    await self.connect()
                    logger.info(
                        f"Successfully connected to '{self.device_alias}' after {attempts + 1} attempt(s)."
                    )
                    # If connect() returns and polling is not enabled, future might not be set.
                    # If polling is disabled, and we want client to exit after first read:
                    if not self.config_manager.get(C.CONFIG_SECTION_DATA, C.CONFIG_KEY_ENABLE_POLLING).lower() == 'true':
                        if self.future and not self.future.done():
                            self.future.set_result("Initial read complete, polling disabled.")
                    return # Successful connection and data reading started (or completed if no poll)
                except DeviceNotFoundError as e:
                    logger.error(
                        f"Attempt {attempts + 1}: Device '{self.device_alias}' not found. {e}"
                    )
                    self.__on_error(e) # Sets future's exception
                    return # No point retrying if device is not found by discover
                except ConnectionError as e:
                    logger.warning(
                        f"Attempt {attempts + 1} to connect to '{self.device_alias}' failed: {e}"
                    )
                    attempts += 1
                    if attempts <= self.connect_retries:
                        logger.info(
                            f"Retrying connection to '{self.device_alias}' in {self.connect_retry_delay} seconds... ({attempts}/{self.connect_retries})"
                        )
                        await asyncio.sleep(self.connect_retry_delay)
                    else:
                        logger.error(
                            f"Max connection retries ({self.connect_retries}) reached for '{self.device_alias}'."
                        )
                        self.__on_error(e) # Sets future's exception
                        return
                except Exception as e: # Catch any other unexpected error during a connection attempt
                    logger.error(
                        f"An unexpected error occurred during connection attempt {attempts + 1} for '{self.device_alias}': {e}",
                        exc_info=True,
                    )
                    self.__on_error(e) # Sets future's exception
                    return
        except asyncio.CancelledError:
            logger.info(f"Connection process for '{self.device_alias}' was cancelled.")
            if self.future and not self.future.done():
                self.future.set_exception(asyncio.CancelledError())


    async def connect(self) -> None:
        """
        Establishes a BLE connection to the configured device.

        Initializes `BLEManager`, discovers the device, connects to it,
        and starts the data reading process by calling `read_section()`.

        Raises:
            DeviceNotFoundError: If the device cannot be found after discovery.
            ConnectionError: If connection to the discovered device fails.
        """
        logger.debug(
            f"Initializing BLEManager for '{self.device_alias}' ({self.device_mac_address})"
        )
        self.ble_manager = BLEManager(
            mac_address=self.device_mac_address,
            alias=self.device_alias,
            on_data=self.on_data_received,
            on_connect_fail=self._on_ble_connect_fail, # Internal handler for BLEM's direct callback
            notify_char_uuid=C.UUID_NOTIFY_CHAR,
            write_char_uuid=C.UUID_WRITE_CHAR,
            write_service_uuid=C.UUID_WRITE_SERVICE,
        )

        logger.debug(f"Starting device discovery for '{self.device_alias}'...")
        try:
            await self.ble_manager.discover()
            self.device = self.ble_manager.device
        except Exception as e: # Catch broad bleak exceptions during discovery
            logger.error(f"BLE discovery for '{self.device_alias}' failed: {e}", exc_info=True)
            raise ConnectionError(f"Discovery failed for {self.device_alias}: {e}") from e

        if not self.device:
            # Message construction already done by BLEManager, this is for BaseClient's context
            error_msg = f"Device '{self.device_alias}' ({self.device_mac_address}) not found by BLEManager after discovery."
            logger.warning(error_msg)
            raise DeviceNotFoundError(error_msg)

        logger.debug(f"Device '{self.device_alias}' found ({self.device.address}), attempting to connect...")
        try:
            await self.ble_manager.connect() # BLEManager handles its own logging for this
        except Exception as e: # Catch broad bleak exceptions during connection
            logger.error(f"BLE connection to '{self.device.address}' ({self.device_alias}) failed: {e}", exc_info=True)
            raise ConnectionError(
                f"Connection to {self.device.address} ({self.device_alias}) failed: {e}"
            ) from e

        if self.ble_manager.client and self.ble_manager.client.is_connected:
            logger.info(
                f"Successfully connected to BLE device: {self.device.address} ('{self.device_alias}')"
            )
            await self.read_section() # Start reading defined data sections
        else:
            # This state should ideally be prevented by exceptions in ble_manager.connect()
            msg = f"Failed to connect to {self.device.address} ('{self.device_alias}'), client not connected post-attempt."
            logger.error(msg)
            raise ConnectionError(msg)

    async def disconnect(self) -> None:
        """
        Disconnects from the BLE device and finalizes the client's future.
        """
        device_identifier = self.device_alias or self.device_mac_address
        logger.info(f"Disconnecting from '{device_identifier}'...")
        if self.ble_manager:
            await self.ble_manager.disconnect() # BLEManager logs its own success/failure
        else:
            logger.debug("No BLEManager instance to disconnect.")

        logger.info(f"Disconnected from '{device_identifier}'.")
        if self.future and not self.future.done():
            logger.debug(f"Setting main future result to 'Disconnected' for '{device_identifier}'.")
            self.future.set_result('Disconnected')


    async def on_data_received(self, response: bytearray) -> None:
        """
        Handles raw data bytes received from the device.

        This method is typically called by `BLEManager` upon receiving a notification.
        It parses the operation code, checks response validity, and routes to the
        appropriate section parser. After all sections are read, it triggers
        `on_read_operation_complete` and schedules the next poll if enabled.

        Args:
            response: The raw bytearray received from the device.
        """
        logger.debug(f"Raw data received by BaseClient for '{self.device_alias}': {response.hex()}")
        if self.read_timeout and not self.read_timeout.cancelled():
            logger.debug(f"Cancelling read timeout for '{self.device_alias}'.")
            self.read_timeout.cancel()

        operation = bytes_to_int(response, 1, 1)
        logger.debug(f"Parsed operation code for '{self.device_alias}': {operation}")

        current_section_def = self.sections[self.section_index]
        register = current_section_def.get(C.KEY_REGISTER, "N/A")

        if operation == C.OP_CODE_READ_SUCCESS or operation == C.OP_CODE_READ_ERROR:
            expected_len = current_section_def[C.KEY_WORDS] * 2 + 5

            if (
                operation == C.OP_CODE_READ_SUCCESS
                and self.section_index < len(self.sections)
                and current_section_def[C.KEY_PARSER] is not None
                and expected_len == len(response)
            ):
                logger.info(
                    f"Read successful for '{self.device_alias}', section {self.section_index} (Register: {register}). Parsing..."
                )
                self.__safe_parser(current_section_def[C.KEY_PARSER], response)
            elif operation == C.OP_CODE_READ_ERROR:
                logger.error(
                    f"Device '{self.device_alias}' returned read error for section {self.section_index} (Register: {register}): {response.hex()}"
                )
                # Optionally, trigger __on_error or a specific error state
            elif not (expected_len == len(response)):
                msg = f"Invalid response length for '{self.device_alias}', section {self.section_index} (Register: {register}): expected {expected_len}, got {len(response)}. Response: {response.hex()}"
                logger.error(msg)
                self.__on_error(InvalidResponseError(msg)) # Treat as critical error for this read cycle
                return # Stop processing this response
            else:  # Should not be reached if logic is sound
                logger.warning(
                    f"Unexpected response for '{self.device_alias}', section {self.section_index} (Register: {register}): {response.hex()}"
                )

            # Check if all sections are read
            if self.section_index >= len(self.sections) - 1:
                logger.info(f"All sections read for '{self.device_alias}'. Read cycle complete.")
                self.section_index = 0 # Reset for next potential cycle
                self.on_read_operation_complete() # Process complete data
                self.data = self._get_empty_data_container() # Prepare for next cycle
                await self.check_polling() # Decide if to poll again
            else:
                self.section_index += 1
                logger.debug(
                    f"Moving to next section {self.section_index} for '{self.device_alias}'. Pausing briefly."
                )
                await asyncio.sleep(0.2)  # Short delay between reading sections, make configurable if needed
                await self.read_section()
        else:
            logger.warning(
                f"Unknown operation code {operation} received by '{self.device_alias}': {response.hex()}"
            )

    def on_read_operation_complete(self) -> None:
        """
        Called when all defined data sections have been successfully read and parsed.

        Adds metadata (`__device`, `__client`) to the collected data object
        and invokes the user-defined `on_data_callback`.
        """
        logger.info(
            f"All sections parsed for '{self.device_alias}'. Preparing data for callback."
        )
        device_alias_val = self.config_manager.get(
            C.CONFIG_SECTION_DEVICE, C.CONFIG_KEY_ALIAS
        )
        client_name_val = self.__class__.__name__

        if isinstance(self.data, dict):
            self.data[C.META_DEVICE_ALIAS] = device_alias_val
            self.data[C.META_CLIENT_NAME] = client_name_val
        else: # Assumed to be a dataclass or similar object
            try:
                setattr(self.data, C.META_DEVICE_ALIAS, device_alias_val)
                setattr(self.data, C.META_CLIENT_NAME, client_name_val)
            except Exception as e: # Broad exception for safety with setattr
                logger.warning(
                    f"Could not set metadata on data object of type {type(self.data)} for '{self.device_alias}': {e}",
                    exc_info=True,
                )
        logger.debug(f"Data for callback for '{self.device_alias}': {self.data}")
        self.__safe_callback(self.on_data_callback, self.data)

    def on_read_timeout(self) -> None:
        """
        Called when a read operation times out.

        Logs the error and triggers the `__on_error` handler with a `ReadTimeoutError`.
        """
        current_register = self.sections[self.section_index].get(C.KEY_REGISTER, 'N/A') if self.sections else 'N/A'
        error_msg = f"Read operation timed out for device '{self.device_alias}' (ID: {self.device_id_from_config}) on section {self.section_index} (Register: {current_register})"
        logger.error(error_msg)
        self.__on_error(ReadTimeoutError(error_msg))

    async def check_polling(self) -> None:
        """
        Checks if polling is enabled and, if so, schedules the next read cycle.
        """
        if (
            self.config_manager.get(
                C.CONFIG_SECTION_DATA, C.CONFIG_KEY_ENABLE_POLLING
            ).lower()
            == "true"
        ):
            poll_interval_s = int(
                self.config_manager.get(
                    C.CONFIG_SECTION_DATA, C.CONFIG_KEY_POLL_INTERVAL
                )
            )
            logger.info(
                f"Polling enabled for '{self.device_alias}'. Waiting {poll_interval_s}s for next read cycle."
            )
            await asyncio.sleep(poll_interval_s)
            logger.debug(
                f"Polling interval ended for '{self.device_alias}'. Starting new read section."
            )
            await self.read_section()
        else:
            logger.info(
                f"Polling disabled for '{self.device_alias}'. Client will not initiate further reads."
            )
            # If not polling, the client's data acquisition loop ends here.
            # The main future in `start()` will eventually be resolved, e.g., by `stop()` or external cancellation.
            if self.future and not self.future.done():
                 self.future.set_result(f"Polling disabled; read cycle for '{self.device_alias}' complete.")


    async def read_section(self) -> None:
        """
        Initiates a read operation for the current data section.
        """
        if not self.sections: # Should not happen if client is correctly implemented
            logger.error(f"No sections defined for {self.__class__.__name__}. Cannot read.")
            return
        if self.section_index >= len(self.sections): # Should be reset before this
            logger.error(f"Section index {self.section_index} out of bounds for {self.device_alias}. Resetting.")
            self.section_index = 0

        current_section_def = self.sections[self.section_index]
        register_to_read = current_section_def[C.KEY_REGISTER]
        words_to_read = current_section_def[C.KEY_WORDS]

        logger.info(
            f"Reading section {self.section_index} for '{self.device_alias}': Register {register_to_read}, Words {words_to_read}"
        )

        self.read_timeout = self.loop.call_later(
            C.DEFAULT_READ_TIMEOUT_S, self.on_read_timeout
        )
        request = self.create_generic_read_request(
            self.device_id_from_config, C.OP_CODE_READ, register_to_read, words_to_read
        )
        if request: # Ensure request was created successfully
            logger.debug(
                f"Sending read request for '{self.device_alias}', section {self.section_index} (Register: {register_to_read}): {request}"
            )
            await self.ble_manager.characteristic_write_value(request)
        else:
            logger.error(f"Failed to create read request for section {self.section_index} (Register: {register_to_read}) for '{self.device_alias}'.")
            # Handle error, perhaps by trying next section or stopping.
            # For now, this will likely lead to a timeout.


    def create_generic_read_request(
        self, device_id: int, function_code: int, register_addr: int, read_word_count: int
    ) -> Optional[bytes]:
        """
        Creates a generic Modbus-like read request payload.

        Args:
            device_id: The Modbus ID of the target device.
            function_code: The Modbus function code (typically 3 for read).
            register_addr: The starting register address.
            read_word_count: The number of words (16-bit registers) to read.

        Returns:
            A bytes object representing the request payload, or None if
            input parameters are invalid.
        """
        if register_addr is None or read_word_count is None:
            logger.warning(
                "Cannot create read request: register_addr or read_word_count is None."
            )
            return None

        payload_list = [
            device_id,
            function_code,
            int_to_bytes(register_addr, 0), # High byte of address
            int_to_bytes(register_addr, 1), # Low byte of address
            int_to_bytes(read_word_count, 0), # High byte of word count
            int_to_bytes(read_word_count, 1), # Low byte of word count
        ]

        crc = crc16_modbus(bytes(payload_list))
        payload_list.extend(crc) # crc is already bytes: [crc_high, crc_low]

        logger.debug(
            f"Created read request payload for device {device_id}, register {register_addr}: {payload_list}"
        )
        return bytes(payload_list)

    def __on_error(self, error: Any) -> None:
        """
        Internal error handler.

        Logs the error, invokes the `on_error_callback`, sets an exception
        on the main future, and attempts to disconnect the BLE manager.

        Args:
            error: The error/exception object or an error message string.
        """
        error_type_name = error.__class__.__name__ if isinstance(error, Exception) else 'UnknownErrorType'
        error_msg = f"Error in {self.__class__.__name__} for '{self.device_alias}': {error_type_name}: {error}"

        # Log with stack trace if it's an actual exception
        if isinstance(error, Exception):
            logger.error(error_msg, exc_info=True)
        else:
            logger.error(error_msg)

        self.__safe_callback(self.on_error_callback, error)

        if self.future and not self.future.done():
            if isinstance(error, Exception):
                self.future.set_exception(error)
            else:  # Wrap non-exception errors (e.g., strings)
                self.future.set_exception(RenogyBTError(str(error)))

        # Attempt graceful disconnect
        if self.ble_manager:
            if self.loop and not self.loop.is_closed() and self.loop.is_running():
                logger.debug(f"Scheduling BLE disconnect for '{self.device_alias}' via loop due to error.")
                self.loop.create_task(self.ble_manager.disconnect())
            elif self.ble_manager.client and self.ble_manager.client.is_connected:
                # Fallback if loop is not available/running (e.g., error during setup)
                logger.debug(
                    f"Running BLE disconnect synchronously for '{self.device_alias}' due to error (loop not available/running)."
                )
                try:
                    asyncio.run(self.ble_manager.disconnect())
                except RuntimeError as e: # e.g. if another loop is already running
                     logger.error(f"RuntimeError during synchronous disconnect for {self.device_alias}: {e}")


    def _on_ble_connect_fail(self, error_message: str) -> None:
        """
        Internal callback for `BLEManager`'s `on_connect_fail`.

        This logs the failure. The actual error handling and retries are managed
        by `_managed_connect`.

        Args:
            error_message: A string describing the connection failure.
        """
        logger.warning(
            f"BLE connection failed for '{self.device_alias}': {error_message}. This will be handled by retry logic."
        )
        # This callback is primarily for BLEManager to inform BaseClient.
        # _managed_connect is responsible for raising ConnectionError and retrying.

    def stop(self) -> None:
        """
        Stops the client operations.

        Cancels any pending read timeouts, schedules disconnection,
        and attempts to resolve the main future to allow the `start()` method
        to exit gracefully.
        """
        logger.info(f"Stop called for client '{self.device_alias}'. Cleaning up...")
        if self.read_timeout and not self.read_timeout.cancelled():
            logger.debug(f"Cancelling active read timeout for '{self.device_alias}'.")
            self.read_timeout.cancel()

        if self.ble_manager:
            if self.loop and self.loop.is_running() and not self.loop.is_closed():
                logger.debug(f"Scheduling disconnect task for '{self.device_alias}' in existing loop.")
                self.loop.create_task(self.disconnect()) # disconnect() will set future
            else:
                try:
                    logger.debug(
                        f"Attempting synchronous disconnect for '{self.device_alias}' as loop is not available/running."
                    )
                    asyncio.run(self.disconnect()) # disconnect() will set future
                except RuntimeError as e:
                    logger.error(f"Error during synchronous disconnect for '{self.device_alias}': {e}", exc_info=True)
                    if self.future and not self.future.done():
                        self.future.set_result(f'STOPPED_WITH_DISCONNECT_ERROR_{e}')
        elif self.future and not self.future.done():
             logger.debug(f"No BLE manager for '{self.device_alias}', setting future to 'STOPPED_PRE_CONNECT'.")
             self.future.set_result('STOPPED_PRE_CONNECT')

        # If disconnect() doesn't resolve the future for some reason, ensure it's done.
        if self.future and not self.future.done():
            logger.debug(f"Ensuring main future for '{self.device_alias}' is resolved in stop().")
            self.future.set_result(f"Client '{self.device_alias}' stopped.")
        logger.info(f"Client stop sequence for '{self.device_alias}' initiated.")


    def __safe_callback(self, callback: Optional[Callable], param: Any) -> None:
        """
        Safely executes a callback function, catching and logging any exceptions.

        Args:
            callback: The callback function to execute.
            param: The parameter to pass to the callback function.
        """
        if callback is not None:
            try:
                logger.debug(
                    f"Executing callback {callback.__name__} for '{self.device_alias}' with param: {param}"
                )
                callback(self, param)
            except Exception as e:
                logger.error(
                    f"Exception in callback {callback.__name__} for '{self.device_alias}': {e}", exc_info=True
                )
                # Important: Do not call self.__on_error from here to avoid potential
                # infinite loops if the error callback itself raises an exception.

    def __safe_parser(self, parser: Callable[[bytearray], None], param: bytearray) -> None:
        """
        Safely executes a parser function, catching and logging exceptions.

        If the parser raises an exception, `__on_error` is called with an
        `InvalidResponseError`.

        Args:
            parser: The parser function to execute.
            param: The bytearray data to pass to the parser.
        """
        if not self.data: # Ensure data container is initialized
            self.data = self._get_empty_data_container()
            logger.debug(f"Re-initialized self.data in __safe_parser for '{self.device_alias}' as it was empty.")

        if parser is not None:
            try:
                logger.debug(f"Executing parser {parser.__name__} for '{self.device_alias}'...")
                parser(param) # Parser methods are expected to update self.data
                logger.debug(f"Parser {parser.__name__} for '{self.device_alias}' executed successfully.")
            except Exception as e:
                logger.error(
                    f"Exception in parser {parser.__name__} for '{self.device_alias}': {e}", exc_info=True
                )
                self.__on_error(
                    InvalidResponseError(
                        f"Error parsing data with {parser.__name__} for '{self.device_alias}': {e}"
                    )
                )

    def _parse_device_info(
        self, response_bytes: bytearray, model_start_index: int, model_end_index: int, strip_chars: Optional[str] = None
    ) -> None:
        """
        Generic parser for device model information.

        Parses the model string from `response_bytes` and updates `self.data.model`.
        Subclasses call this from their specific section parsers.

        Args:
            response_bytes: The bytearray containing the response from the device.
            model_start_index: The starting index of the model string in `response_bytes`.
            model_end_index: The ending index of the model string.
            strip_chars: Optional characters to strip from the decoded model string.
        """
        if not self.data: # Should be initialized by _get_empty_data_container
            logger.warning(f"_parse_device_info called for '{self.device_alias}' but self.data is not initialized. Attempting to initialize.")
            self.data = self._get_empty_data_container()

        logger.debug(f"Parsing device info (model) from response for '{self.device_alias}'.")
        raw_model = response_bytes[model_start_index:model_end_index]
        model_str = "Unknown"
        try:
            model_str = raw_model.decode("utf-8")
            if strip_chars:
                model_str = model_str.strip(strip_chars)
            else:
                model_str = model_str.strip()
            logger.debug(f"Parsed model for '{self.device_alias}': {model_str}")
        except UnicodeDecodeError:
            logger.warning(f"Could not decode model string from raw for '{self.device_alias}': {raw_model.hex()}")

        if hasattr(self.data, C.KEY_MODEL):
            setattr(self.data, C.KEY_MODEL, model_str) # Use setattr for dataclasses
        else:
            logger.warning(
                f"_parse_device_info: self.data (type: {type(self.data)}) for '{self.device_alias}' has no '{C.KEY_MODEL}' attribute."
            )


    def _parse_device_address(
        self, response_bytes: bytearray, address_start_index: int, address_length_bytes: int
    ) -> None:
        """
        Generic parser for device Modbus ID.

        Parses the device ID from `response_bytes` and updates `self.data.device_id`.
        Compares with `self.device_id_from_config` and logs a warning if different.

        Args:
            response_bytes: The bytearray containing the response from the device.
            address_start_index: The starting index of the device ID in `response_bytes`.
            address_length_bytes: The length of the device ID in bytes.
        """
        if not self.data: # Should be initialized
            logger.warning(f"_parse_device_address called for '{self.device_alias}' but self.data is not initialized. Attempting to initialize.")
            self.data = self._get_empty_data_container()

        logger.debug(f"Parsing device address (ID) from response for '{self.device_alias}'.")
        device_id_from_device = bytes_to_int(
            response_bytes, address_start_index, address_length_bytes
        )
        logger.debug(f"Parsed device ID from device for '{self.device_alias}': {device_id_from_device}")

        if hasattr(self.data, C.KEY_DEVICE_ID):
            setattr(self.data, C.KEY_DEVICE_ID, int(device_id_from_device)) # Ensure it's int
        else:
            logger.warning(
                f"_parse_device_address: self.data (type: {type(self.data)}) for '{self.device_alias}' has no '{C.KEY_DEVICE_ID}' attribute."
            )

        if self.device_id_from_config != device_id_from_device:
            logger.warning(
                f"Device ID mismatch for '{self.device_alias}': Configured ID {self.device_id_from_config}, ID from device {device_id_from_device}."
            )

    def _get_empty_data_container(self) -> Any:
        """
        Returns an empty container for storing parsed device data.

        Subclasses (device-specific clients) should override this method to return
        an instance of their specific data dataclass (e.g., `RoverData()`).
        The base implementation returns an empty dictionary for clients that might
        not have been updated to use dataclasses.

        Returns:
            An empty dictionary or a device-specific dataclass instance.
        """
        logger.debug(f"BaseClient._get_empty_data_container() called for '{self.device_alias}', returning dict.")
        return {}
