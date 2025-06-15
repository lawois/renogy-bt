# -*- coding: utf-8 -*-
"""
renogybt.BLEManager
~~~~~~~~~~~~~~~~~~~

This module provides the `BLEManager` class, which handles the low-level
Bluetooth Low Energy (BLE) communication with Renogy devices. It uses the `bleak`
library for discovering, connecting, and interacting with BLE devices.

The `BLEManager` is responsible for:
- Discovering devices by MAC address or alias.
- Establishing and managing a connection to a device.
- Subscribing to notifications for data reception.
- Writing data to device characteristics.
- Handling disconnections.
"""
import asyncio
import logging
import sys
from bleak import BleakClient, BleakScanner, BLEDevice
from typing import Callable, List, Optional # For type hinting

# Using module-level logger
logger = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 5  # Max wait time for Bluetooth scanning in seconds


class BLEManager:
    """
    Manages BLE connection and communication with a Renogy device.

    This class encapsulates `bleak` library functionalities to discover, connect,
    read from, and write to Renogy devices. It handles service and characteristic
    discovery specific to the Renogy communication protocol.

    Args:
        mac_address (str): The MAC address of the target device.
        alias (str): The alias (Bluetooth name) of the target device. Used as an
                     alternative to MAC address for discovery.
        on_data (Callable[[bytearray], None]): Async callback function to be invoked
                                               when data is received from the device.
        on_connect_fail (Callable[[ExceptionInfo], None]): Callback function to be
                                                           invoked if connection fails.
                                                           Receives exception info.
        write_service_uuid (str): UUID of the GATT service for writing commands.
        notify_char_uuid (str): UUID of the GATT characteristic for notifications.
        write_char_uuid (str): UUID of the GATT characteristic for writing commands.
    """

    def __init__(
        self,
        mac_address: str,
        alias: str,
        on_data: Callable[[bytearray], asyncio.Future], # Should be async callable
        on_connect_fail: Callable[[Optional[tuple], str], None], # Adjusted for potential string message
        write_service_uuid: str,
        notify_char_uuid: str,
        write_char_uuid: str,
    ):
        self.mac_address: str = mac_address.upper() # Normalize MAC address
        self.device_alias: str = alias
        self.data_callback: Callable[[bytearray], asyncio.Future] = on_data
        self.connect_fail_callback: Callable[[Optional[tuple], str], None] = on_connect_fail
        self.write_service_uuid: str = write_service_uuid
        self.notify_char_uuid: str = notify_char_uuid
        self.write_char_uuid: str = write_char_uuid

        self.write_char_handle: Optional[int] = None # Handle for the write characteristic
        self.device: Optional[BLEDevice] = None # Discovered bleak device object
        self.client: Optional[BleakClient] = None # Active BleakClient instance
        self.discovered_devices: List[BLEDevice] = [] # List of devices found during scan
        logger.debug(f"BLEManager initialized for MAC: {self.mac_address}, Alias: {self.device_alias}")


    async def discover(self) -> None:
        """
        Discovers Bluetooth devices and attempts to find the target device.

        Scans for BLE devices for `DISCOVERY_TIMEOUT` seconds. If a device
        matches the configured MAC address or alias, it's set as `self.device`.
        """
        logger.info(f"Starting BLE discovery for MAC '{self.mac_address}' or alias '{self.device_alias}'...")
        try:
            self.discovered_devices = await BleakScanner.discover(
                timeout=DISCOVERY_TIMEOUT
            )
        except Exception as e:
            logger.error(f"Error during BleakScanner.discover: {e}", exc_info=True)
            # Propagate or handle as a discovery failure
            return

        logger.info(f"Discovery finished. Found {len(self.discovered_devices)} devices.")
        logger.debug(f"Discovered devices: {[d.address for d in self.discovered_devices]}")


        for dev in self.discovered_devices:
            # Ensure dev.address is not None before calling upper()
            dev_address_upper = dev.address.upper() if dev.address else ""
            dev_name_stripped = dev.name.strip() if dev.name else ""

            if dev.address is not None and (
                dev_address_upper == self.mac_address
                or (dev.name and dev_name_stripped == self.device_alias)
            ):
                logger.info(f"Found matching device: Name='{dev.name}', Address='{dev.address}'")
                self.device = dev
                return # Found the device, no need to continue loop

        logger.warning(f"Target device MAC '{self.mac_address}' or alias '{self.device_alias}' not found in scan results.")


    async def connect(self) -> None:
        """
        Connects to the discovered device and sets up notifications.

        If no device has been set by `discover()`, this method will log an error
        and return. It attempts to connect to `self.device`, then subscribes to
        notifications on the `notify_char_uuid` and identifies the handle for
        `write_char_uuid`.
        """
        if not self.device:
            logger.error("Cannot connect: No device discovered or set.")
            # Call connect_fail_callback or raise an exception if appropriate
            # self.connect_fail_callback(None, "No device discovered to connect to.")
            return

        logger.info(f"Attempting to connect to device: {self.device.address} (Alias: {self.device_alias})")
        self.client = BleakClient(self.device)
        try:
            await self.client.connect()
            logger.info(
                f"Successfully connected to {self.device.address}. Client connected: {self.client.is_connected}"
            )
            if not self.client.is_connected: # Should not happen if connect() succeeded without exception
                logger.error(f"Connection to {self.device.address} failed unexpectedly after connect call.")
                self.connect_fail_callback(None, f"Unable to connect to {self.device.address}")
                return

            logger.debug("Discovering services and characteristics...")
            for service in self.client.services:
                logger.debug(f"Service found: {service.uuid}")
                for characteristic in service.characteristics:
                    logger.debug(f"  Characteristic found: {characteristic.uuid} (Handle: {characteristic.handle})")
                    if characteristic.uuid == self.notify_char_uuid:
                        logger.info(
                            f"Subscribing to notifications on characteristic {characteristic.uuid}"
                        )
                        await self.client.start_notify(
                            characteristic, self.notification_callback
                        )
                    if (
                        characteristic.uuid == self.write_char_uuid
                        and service.uuid == self.write_service_uuid
                    ):
                        self.write_char_handle = characteristic.handle
                        logger.info(
                            f"Found write characteristic {characteristic.uuid} (Handle: {self.write_char_handle}) on service {service.uuid}"
                        )

            if self.write_char_handle is None:
                logger.warning(f"Write characteristic {self.write_char_uuid} not found on service {self.write_service_uuid}.")
                # This might be an issue depending on whether writing is always required.

        except Exception as e:
            logger.error(f"Error connecting to device {self.device.address}: {e}", exc_info=True)
            self.connect_fail_callback(sys.exc_info(), str(e)) # Pass both exc_info and string message

    async def notification_callback(
        self, characteristic_handle: int, data: bytearray
    ) -> None:
        """
        Callback invoked by `bleak` when a notification is received.

        Args:
            characteristic_handle: The handle of the characteristic that sent the notification.
                                   (Currently unused, but provided by bleak)
            data: The received data as a bytearray.
        """
        logger.debug(f"Notification received on handle {characteristic_handle}: {data.hex()}")
        await self.data_callback(data)

    async def characteristic_write_value(self, data: bytearray) -> None:
        """
        Writes data to the configured write characteristic.

        Args:
            data: The bytearray data to write to the device.
        """
        if not self.client or not self.client.is_connected:
            logger.error("Cannot write: Client not connected.")
            return
        if self.write_char_handle is None:
            logger.error(f"Cannot write: Write characteristic handle for {self.write_char_uuid} not found.")
            return

        try:
            logger.debug(f"Writing to characteristic {self.write_char_uuid} (Handle: {self.write_char_handle}): {data.hex()}")
            await self.client.write_gatt_char(
                self.write_char_handle, data, response=False # Renogy devices often don't use write-with-response
            )
            logger.info("Characteristic write successful.")
            # Brief pause can sometimes help ensure command is processed by device
            # before sending another, though not always necessary.
            await asyncio.sleep(0.1) # Reduced from 0.5, make configurable if needed.
        except Exception as e:
            logger.error(f"Characteristic write to {self.write_char_uuid} failed: {e}", exc_info=True)
            # Potentially raise an exception or call an error callback here

    async def disconnect(self) -> None:
        """Disconnects from the currently connected device."""
        if self.client and self.client.is_connected:
            logger.info(
                f"Disconnecting from device: {self.device.name if self.device else 'Unknown'} ({self.client.address})"
            )
            try:
                await self.client.disconnect()
                logger.info("Successfully disconnected.")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}", exc_info=True)
        else:
            logger.info("Client not connected or already disconnected.")
        self.client = None # Clear client instance
        self.device = None # Clear device instance (optional, depends on reconnect logic)
