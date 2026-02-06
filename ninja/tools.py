"""
NinjaRMM Tool Definitions for Claude

Defines the tools that Claude can use to query NinjaRMM device data.
These follow Claude's tool definition format and are used by the proxy agent.
"""

from typing import List, Dict, Any


def get_ninja_tools() -> List[Dict[str, Any]]:
    """
    Get the list of NinjaRMM tools available to Claude.

    Returns:
        List of tool definitions in Claude format
    """
    return [
        {
            "name": "ninja_get_device",
            "description": (
                "Get device details from NinjaRMM including name, OS, "
                "online/offline status, IP addresses, model, and last contact time."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "integer",
                        "description": "The NinjaRMM device ID",
                    }
                },
                "required": ["device_id"],
            },
        },
        {
            "name": "ninja_get_device_volumes",
            "description": (
                "Get disk volume information for a device from NinjaRMM "
                "including drive letters, capacity, free space, and filesystem type."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "integer",
                        "description": "The NinjaRMM device ID",
                    }
                },
                "required": ["device_id"],
            },
        },
        {
            "name": "ninja_get_device_alerts",
            "description": (
                "Get active alerts/triggered conditions for a device from NinjaRMM. "
                "Shows current problems and monitoring alerts."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "integer",
                        "description": "The NinjaRMM device ID",
                    }
                },
                "required": ["device_id"],
            },
        },
        {
            "name": "ninja_get_device_os_patches",
            "description": (
                "Get pending OS patches for a device from NinjaRMM. "
                "Shows which Windows/OS updates are waiting to be installed."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "integer",
                        "description": "The NinjaRMM device ID",
                    }
                },
                "required": ["device_id"],
            },
        },
        {
            "name": "ninja_get_device_software",
            "description": (
                "Get installed software list for a device from NinjaRMM. "
                "Use this to check if specific software is installed or verify versions."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "integer",
                        "description": "The NinjaRMM device ID",
                    }
                },
                "required": ["device_id"],
            },
        },
        {
            "name": "ninja_get_device_processors",
            "description": (
                "Get CPU/processor details for a device from NinjaRMM "
                "including model, core count, and clock speed."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "integer",
                        "description": "The NinjaRMM device ID",
                    }
                },
                "required": ["device_id"],
            },
        },
        {
            "name": "ninja_get_device_last_user",
            "description": (
                "Get the last logged-on user for a device from NinjaRMM."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "integer",
                        "description": "The NinjaRMM device ID",
                    }
                },
                "required": ["device_id"],
            },
        },
        {
            "name": "ninja_get_device_disk_drives",
            "description": (
                "Get physical disk drive details for a device from NinjaRMM "
                "including model, size, interface type, and media type (SSD/HDD)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "integer",
                        "description": "The NinjaRMM device ID",
                    }
                },
                "required": ["device_id"],
            },
        },
        {
            "name": "ninja_get_device_network_interfaces",
            "description": (
                "Get network interface details for a device from NinjaRMM "
                "including IP configuration, MAC addresses, and connection status."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "integer",
                        "description": "The NinjaRMM device ID",
                    }
                },
                "required": ["device_id"],
            },
        },
        {
            "name": "ninja_get_device_windows_services",
            "description": (
                "Get Windows services list for a device from NinjaRMM "
                "including service name, status, and startup type."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "integer",
                        "description": "The NinjaRMM device ID",
                    }
                },
                "required": ["device_id"],
            },
        },
    ]
