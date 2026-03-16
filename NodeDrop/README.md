# NodeDrop

Portable LAN file and folder transfer application built with Python and PySide6.

## Overview

NodeDrop is a lightweight desktop application designed to transfer files and folders between computers connected to the same local network.

It follows a simple and maintainable V1 architecture, with:
- LAN peer discovery
- TCP session-based communication
- password authentication
- file and folder transfer
- transfer progress and telemetry
- transfer cancellation support

## Features

- Automatic peer discovery on the local network
- File transfer
- Folder transfer
- Transfer progress display
- Transfer telemetry display
- Transfer cancellation
- Portable Windows build

## Tech stack

- Python 3
- PySide6
- UDP for LAN discovery
- TCP for sessions and transfers
- JSON-based messages
- PyInstaller for packaging

## Status

NodeDrop V1 is functionally validated on its main scope.

Validated behaviors include:
- application startup
- LAN discovery
- peer detection
- TCP authentication
- small file transfer
- large file transfer
- folder transfer
- bidirectional real-world testing
- transfer cancellation
- new transfer after cancellation
- packaged executable validation

## Known limitation

NodeDrop V1 does not properly support simultaneous bidirectional transfers between the same two running instances.

Example of unsupported usage:
- Machine A sends a file to Machine B
- while Machine B sends another file to Machine A at the same time

The application is intended for simple, sequential transfers in one direction at a time.

## Repository contents

This repository contains the source code and documentation.

Portable packaged builds are intended to be distributed separately through GitHub Releases.

## License

MIT License