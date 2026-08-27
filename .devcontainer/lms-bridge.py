#!/usr/bin/env python3
"""Narrow TCP bridge between a Dev Container and host LM Studio."""

from __future__ import annotations

import argparse
import json
import socket
import socketserver
import subprocess
import threading
from pathlib import Path


def copy_stream(source: socket.socket, destination: socket.socket) -> None:
	try:
		while data := source.recv(65536):
			destination.sendall(data)
	except OSError:
		pass
	finally:
		try:
			destination.shutdown(socket.SHUT_WR)
		except OSError:
			pass


def container_gateway() -> str:
	with Path("/proc/net/route").open(encoding="ascii") as routes:
		next(routes)
		for route in routes:
			fields = route.split()
			if fields[1] == "00000000":
				gateway = bytes.fromhex(fields[2])
				return socket.inet_ntoa(gateway[::-1])
	raise RuntimeError("could not find the container's default gateway")


class Bridge(socketserver.ThreadingTCPServer):
	allow_reuse_address = True
	daemon_threads = True

	def __init__(
		self,
		listen: tuple[str, int],
		*,
		target,
		allowed_peers=None,
	) -> None:
		self.target = target
		self.allowed_peers = allowed_peers
		super().__init__(listen, BridgeHandler)


class BridgeHandler(socketserver.BaseRequestHandler):
	def handle(self) -> None:
		peer = self.client_address[0]
		if self.server.allowed_peers is not None and peer not in self.server.allowed_peers():
			return

		try:
			upstream = socket.create_connection(self.server.target(), timeout=5)
		except (OSError, ValueError, json.JSONDecodeError):
			return

		with upstream:
			outbound = threading.Thread(target=copy_stream, args=(self.request, upstream))
			outbound.start()
			copy_stream(upstream, self.request)
			outbound.join()


def docker_container_ips(docker: str, project: str) -> set[str]:
	containers = subprocess.run(
		[
			docker,
			"ps",
			"--quiet",
			"--filter",
			f"label=com.docker.compose.project={project}",
			"--filter",
			"label=com.docker.compose.service=frappe",
		],
		check=False,
		capture_output=True,
		text=True,
	).stdout.split()
	if not containers:
		return set()

	result = subprocess.run(
		[
			docker,
			"inspect",
			"--format",
			"{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}",
			*containers,
		],
		check=False,
		capture_output=True,
		text=True,
	)
	return set(result.stdout.split())


def control_target(info_path: Path) -> tuple[str, int]:
	info = json.loads(info_path.read_text(encoding="utf-8"))
	port = int(info["port"])
	if not 1 <= port <= 65535:
		raise ValueError("invalid LM Studio control port")
	return "127.0.0.1", port


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser()
	parser.add_argument("mode", choices=("host", "container"))
	parser.add_argument("--control-port", type=int, required=True)
	parser.add_argument("--api-bridge-port", type=int, required=True)
	parser.add_argument("--api-port", type=int, required=True)
	parser.add_argument("--project")
	parser.add_argument("--docker")
	parser.add_argument("--info", type=Path)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	if args.mode == "host":
		if not args.project or not args.docker or not args.info:
			raise SystemExit("host mode requires --project, --docker, and --info")
		allowed_peers = lambda: docker_container_ips(args.docker, args.project)
		control_bridge = Bridge(
			("0.0.0.0", args.control_port),
			target=lambda: control_target(args.info),
			allowed_peers=allowed_peers,
		)
		api_bridge = Bridge(
			("0.0.0.0", args.api_bridge_port),
			target=lambda: ("127.0.0.1", args.api_port),
			allowed_peers=allowed_peers,
		)
	else:
		gateway = container_gateway()
		control_bridge = Bridge(
			("127.0.0.1", args.control_port),
			target=lambda: (gateway, args.control_port),
		)
		api_bridge = Bridge(
			("127.0.0.1", args.api_port),
			target=lambda: (gateway, args.api_bridge_port),
		)

	control_thread = threading.Thread(target=control_bridge.serve_forever, daemon=True)
	control_thread.start()
	with control_bridge, api_bridge:
		api_bridge.serve_forever()


if __name__ == "__main__":
	main()
