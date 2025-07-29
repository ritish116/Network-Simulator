# Network-Simulator


## Table of Contents
1. [Overview](#overview)
2. [Application Layer](#1-application-layer)
3. [Transport Layer](#2-transport-layer)
4. [Network Layer](#3-network-layer)
5. [Data Link Layer](#4-data-link-layer)
6. [Physical Layer](#5-physical-layer)
7. [Example Data Flow](#example-data-flow-sending-data)
8. [Summary Table](#summary-table)

---

## Overview
This document explains how the five layers of the OSI model are implemented in the `network_simulator_main.py` code. It details the main classes, functions, and protocols/mechanisms used at each layer, with code snippets and explanations.

---

## 1. Application Layer

**Purpose:** Provides network services to end-user applications (e.g., file transfer, remote login).

**Implemented Protocols:**
- **FTP (File Transfer Protocol)**
- **Telnet (Remote Command Execution)**

**Key Classes/Functions:**
- `ApplicationLayer` class

### FTP Service (Simulated)
```python
class ApplicationLayer:
    def ftp_service(self, host, port, username=None, password=None):
        # ...
        ftp = MockFTP(host, port)
        ftp.connect(host, port)
        if username and password:
            ftp.login(username, password)
        else:
            ftp.login()
        return ftp
```
**Explanation:** This function simulates starting an FTP service on a device. The `MockFTP` class is used to mimic FTP operations for file transfer.

### Telnet Service (Simulated)
```python
    def telnet_service(self, host, port, username=None, password=None):
        class MockTelnet:
            def __init__(self, host, port):
                self.host = host
                self.port = port
                self.connected = True
            def write(self, data):
                print(f"[MOCK TELNET] Sent: {data}")
            def read_until(self, expected, timeout=5):
                return b"[MOCK TELNET] Response\n"
            def close(self):
                self.connected = False
        return MockTelnet(host, port)
```
**Explanation:** This function simulates a Telnet service for remote command execution.

### File Transfer and Command Execution
```python
    def send_file_ftp(self, ftp_connection, local_file, remote_file):
        with open(local_file, 'rb') as file:
            ftp_connection.storbinary(f'STOR {remote_file}', file)
```
**Explanation:** Simulates sending a file using FTP.

---

## 2. Transport Layer

**Purpose:** Provides reliable data transfer, flow control, and multiplexing between processes.

**Implemented Protocols:**
- **Go-Back-N (GBN) ARQ** (reliable, sliding window protocol)
- **Port Management**

**Key Classes/Functions:**
- `TransportLayer` class

### Go-Back-N (GBN) Protocol
```python
class TransportLayer:
    def send_segments_gbn(self, data, source_port, dest_port):
        segments = []
        data_size = len(data)
        chunk_size = 10  # Characters per segment
        for i in range(0, data_size, chunk_size):
            chunk = data[i:i+chunk_size]
            segment = self.create_segment(chunk, source_port, dest_port, self.sequence_number)
            segments.append(segment)
            self.sequence_number = (self.sequence_number + 1) % 8
        # Send initial window of segments
        window_end = min(self.window_size, len(segments))
        for i in range(window_end):
            segment = segments[i]
            print(f"📤 Sending segment {segment['sequence']} (Initial Window)")
            self.next_seq_num = (self.next_seq_num + 1) % 8
        return segments
```
**Explanation:** Splits data into segments, assigns sequence numbers, and sends them using a sliding window (GBN protocol).

### Port Management
```python
    def assign_port(self, process_name, is_well_known=False):
        if is_well_known and process_name in self.well_known_ports:
            port = self.well_known_ports[process_name]
            # ...
            return port
        # Assign ephemeral port otherwise
        while True:
            port = random.randint(*self.ephemeral_port_range)
            if port not in self.used_ports:
                self.used_ports.add(port)
                # ...
                return port
```
**Explanation:** Assigns ports to processes/services, supporting both well-known and ephemeral ports.

---

## 3. Network Layer

**Purpose:** Handles logical addressing, routing, and forwarding of packets between devices.

**Implemented Protocols/Mechanisms:**
- **IP Addressing and Subnetting**
- **Routing (RIP - Routing Information Protocol)**
- **Longest Common Prefix (LCP) Routing**

**Key Classes/Functions:**
- `NetworkSimulator` class

### IP Assignment
```python
    def assign_ip(self, device_name, ip_with_mask):
        ip_interface = ipaddress.ip_interface(ip_with_mask)
        self.ip_addresses[device_name] = str(ip_interface.ip)
        self.subnet_masks[device_name] = str(ip_interface.netmask)
        # ...
```
**Explanation:** Assigns an IP address and subnet mask to a device.

### RIP Routing Table Initialization
```python
    def initialize_router_table(self, router):
        for neighbor in self.connections[router]:
            if neighbor in self.ip_addresses:
                # ...
                self.routing_tables[router].append({
                    'destination': neighbor,
                    'next_hop': neighbor,
                    'hop_count': 1,
                    'prefix': network,
                    'prefix_len': prefix_len,
                    'lcp_length': lcp_length
                })
```
**Explanation:** Initializes the routing table for a router with directly connected networks.

### LCP Routing
```python
    def find_longest_common_prefix(self, ip_address):
        ip = ipaddress.ip_address(ip_address)
        best_match = None
        best_length = -1
        for device, prefix_info in self.ip_prefixes.items():
            network = ipaddress.ip_network(prefix_info['network'])
            if ip in network:
                if prefix_info['prefix_len'] > best_length:
                    best_length = prefix_info['prefix_len']
                    best_match = device
        return best_match
```
**Explanation:** Finds the device with the longest common prefix match for a given IP address (used for routing decisions).

---

## 4. Data Link Layer

**Purpose:** Provides node-to-node data transfer, MAC addressing, error detection, and manages access to the physical medium.

**Implemented Protocols/Mechanisms:**
- **Go-Back-N (GBN) ARQ**
- **CSMA/CD (Carrier Sense Multiple Access with Collision Detection)**
- **MAC Addressing**
- **CRC (Cyclic Redundancy Check)**
- **Switch/Bridge MAC Learning**
- **ARP (Address Resolution Protocol)**

**Key Classes/Functions:**
- `DataLinkLayer` class

### Go-Back-N (GBN) Frame Sending
```python
class DataLinkLayer:
    def send_frames_gbn(self, data_list):
        self.buffer = []
        for i, data in enumerate(data_list):
            frame = self.create_frame(data, i % 8)
            self.buffer.append(frame)
        window_end = min(self.window_size, len(self.buffer))
        for i in range(window_end):
            frame = self.buffer[i]
            print(f"📤 Sending frame {frame['sequence']} (Initial Window)")
            self.next_seq_num = (self.next_seq_num + 1) % 8
        return self.buffer[:window_end]
```
**Explanation:** Buffers and sends frames using the GBN protocol with a sliding window.

### CSMA/CD (Channel Access)
```python
    def csma_cd(self):
        max_sensing_attempts = 5
        sensing_attempts = 0
        while sensing_attempts < max_sensing_attempts:
            if self.sense_channel():
                print(" Channel is clear, starting transmission...")
                self.is_transmitting = True
                time.sleep(self.collision_window)
                if self.detect_collision():
                    print(" Collision detected!")
                    # ... handle collision ...
                    continue
                print("✅ Transmission completed successfully")
                self.is_transmitting = False
                return True
            else:
                print("🔄 Channel busy, waiting...")
                time.sleep(0.5)
                sensing_attempts += 1
        print("❌ Channel persistently busy, transmission failed")
        return False
```
**Explanation:** Simulates CSMA/CD for channel access and collision detection.

### MAC Address Generation
```python
    def generate_mac_address(self):
        return ':'.join(['{:02x}'.format(random.randint(0, 255)) for _ in range(6)])
```
**Explanation:** Generates a random MAC address for each device.

### CRC for Error Detection
```python
    def calculate_crc(self, data):
        return hashlib.md5(data.encode()).hexdigest()
    def check_crc(self, data, received_crc):
        return self.calculate_crc(data) == received_crc
```
**Explanation:** Uses MD5 as a stand-in for CRC to detect errors in frames.

### ARP Table Update
```python
class NetworkSimulator:
    def update_arp_table(self, device_name, ip_address, mac_address):
        self.arp_tables[device_name][ip_address] = mac_address
        self.arp_timestamps[device_name][ip_address] = time.time()
        print(f"✅ Updated ARP table for {device_name}: {ip_address} -> {mac_address}")
```
**Explanation:** Updates the ARP table for a device, mapping IP addresses to MAC addresses.

---

## 5. Physical Layer

**Purpose:** Simulates the transmission of raw bits over a physical medium.

**Implemented Mechanisms:**
- **Physical transmission is abstracted** (no actual bit-level simulation, but logical/log message representation is provided).

**Key Classes/Functions:**
- `NetworkSimulator.send_data()` and related methods:
```python
    def send_data(self, sender, receiver, message):
        # ...
        print("\n5. Physical Layer:")
        print(f"  Data being transmitted through physical medium")
        # ...
```
**Explanation:** The physical layer is represented by print statements indicating data transmission.

---

## Example Data Flow (Sending Data)

Suppose a user sends a file from DeviceA to DeviceB using FTP:

1. **Application Layer:**
   - `ApplicationLayer.ftp_service()` is called to start FTP on DeviceA.
   - `ApplicationLayer.send_file_ftp()` is used to send the file.
2. **Transport Layer:**
   - `TransportLayer.send_segments_gbn()` splits the file into segments and sends them using GBN.
3. **Network Layer:**
   - `NetworkSimulator.route_packet()` determines the path using IP, RIP, and LCP.
4. **Data Link Layer:**
   - `DataLinkLayer.send_frames_gbn()` frames each segment, uses CSMA/CD for channel access, and ARP for MAC resolution.
   - `DataLinkLayer.calculate_crc()` and `check_crc()` ensure error detection.
5. **Physical Layer:**
   - `NetworkSimulator.send_data()` prints/logs the transmission, representing the physical layer.

---

## Summary Table

| Layer             | Main Class(es)         | Protocols/Mechanisms Simulated                |
|-------------------|------------------------|-----------------------------------------------|
| Application       | ApplicationLayer       | FTP, Telnet                                  |
| Transport         | TransportLayer         | Go-Back-N, Port Management                    |
| Network           | NetworkSimulator       | IP, RIP, LCP, Routing, Subnetting            |
| Data Link         | DataLinkLayer          | Go-Back-N, CSMA/CD, MAC, CRC, ARP, Switching |
| Physical          | NetworkSimulator       | Abstracted (print/logical representation)     |

---

For more details, refer to the respective class and method docstrings in the code. 
