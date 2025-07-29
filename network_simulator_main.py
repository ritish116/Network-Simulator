import networkx as nx
import matplotlib.pyplot as plt
import random
import hashlib
import time
from enum import Enum
import ipaddress
import socket
import threading
import ftplib
import os
from collections import deque


class DeviceType(Enum):
    END_DEVICE = 1
    HUB = 2
    BRIDGE = 3
    SWITCH = 4
    ROUTER = 5  # Added router device type


class DataLinkLayer:
    def __init__(self):
        self.mac_address = self.generate_mac_address()
        self.collision_detected = False
        self.backoff_time = 0
        self.transmission_attempts = 0
        self.max_attempts = 16  # Maximum number of transmission attempts
        self.sequence_number = 0  # Current sequence number
        self.expected_sequence = 0  # Expected sequence number
        self.timeout = 2.0  # Timeout for acknowledgment in seconds
        self.last_sent_time = 0
        self.last_received_time = 0
        self.is_transmitting = False
        self.channel_busy = False
        self.collision_window = 0.1
        # Go-Back-N parameters
        self.window_size = 4  # Size of the sliding window
        self.base = 0  # Base of the window
        self.next_seq_num = 0  # Next sequence number to be used
        self.buffer = []  # Buffer for storing frames
        self.ack_received = set()  # Set to track received acknowledgments
        self.last_cumulative_ack = -1  # Track last cumulative acknowledgment

    def generate_mac_address(self):
        """Generate a random MAC address."""
        return ':'.join(['{:02x}'.format(random.randint(0, 255)) for _ in range(6)])

    def calculate_crc(self, data):
        """Calculate CRC-32 for error detection."""
        return hashlib.md5(data.encode()).hexdigest()

    def check_crc(self, data, received_crc):
        """Verify CRC of received data."""
        calculated_crc = self.calculate_crc(data)
        return calculated_crc == received_crc

    def create_frame(self, data, seq_num):
        """Create a frame with sequence number and CRC."""
        frame = {
            'sequence': seq_num,
            'data': data,
            'crc': self.calculate_crc(data)
        }
        return frame

    def is_within_window(self, seq_num):
        """Check if sequence number is within the current window."""
        return self.base <= seq_num < self.base + self.window_size

    def send_frames_gbn(self, data_list):
        """Send multiple frames using Go-Back-N protocol with cumulative ACK."""
        self.buffer = []
        frames_sent = []
        
        # Create and buffer all frames
        for i, data in enumerate(data_list):
            frame = self.create_frame(data, i % 8)  # Use modulo 8 for sequence numbers
            self.buffer.append(frame)
        
        # Send initial window of frames
        window_end = min(self.window_size, len(self.buffer))
        for i in range(window_end):
            frame = self.buffer[i]
            print(f"📤 Sending frame {frame['sequence']} (Initial Window)")
            frames_sent.append(frame)
            self.next_seq_num = (self.next_seq_num + 1) % 8 #increment the sequence number
        
        return frames_sent

    def receive_frame_gbn(self, frame):
        """Receive a frame using Go-Back-N protocol with cumulative ACK."""
        if self.check_crc(frame['data'], frame['crc']):
            if frame['sequence'] == self.expected_sequence:
                print(f"✅ Received frame {frame['sequence']} successfully")
                self.expected_sequence = (self.expected_sequence + 1) % 8
                return True, frame['sequence']
            else:
                print(f"❌ Expected frame {self.expected_sequence}, got frame {frame['sequence']}")
                return False, self.expected_sequence
        return False, self.expected_sequence

    def handle_ack_gbn(self, ack_num):
        """Handle cumulative acknowledgment in Go-Back-N protocol."""
        if ack_num > self.base: #if the ack number is greater than or equal to the base sequence number
            print(f"📥 Received cumulative ACK {ack_num}")
            self.last_cumulative_ack = ack_num
            
            # Move window based on cumulative ACK
            while self.base <ack_num:
                if self.base in self.ack_received:
                    self.ack_received.remove(self.base)
                self.base = (self.base + 1) % 8
                print(f"🔄 Window moved, new base: {self.base}")
            
            # Send more frames if window has space
            if len(self.buffer) > 0:
                next_frame_index = (self.next_seq_num - self.base) % len(self.buffer)
                if next_frame_index < len(self.buffer):
                    frame = self.buffer[next_frame_index]
                    print(f"📤 Sending additional frame {frame['sequence']}")
                    self.next_seq_num = (self.next_seq_num + 1) % 8

    def sense_channel(self):
        """Sense if the channel is busy (CSMA)."""
        self.channel_busy = random.random() < 0.3
        return not self.channel_busy

    def detect_collision(self):
        """Detect if a collision occurred during transmission."""
        if self.is_transmitting:
            collision_prob = 0.2
            return random.random() < collision_prob
        return False

    def csma_cd(self):
        """Implement CSMA/CD protocol with exponential backoff."""
        max_sensing_attempts = 5
        sensing_attempts = 0

        while sensing_attempts < max_sensing_attempts:
            if self.sense_channel():
                print(" Channel is clear, starting transmission...")
                self.is_transmitting = True

                time.sleep(self.collision_window) #wait for the collision window to pass
                if self.detect_collision():
                    print(" Collision detected!")
                    self.collision_detected = True
                    self.is_transmitting = False

                    if self.transmission_attempts >= self.max_attempts:
                        print("❌ Maximum transmission attempts reached. Aborting.")
                        return False

                    self.transmission_attempts += 1
                    backoff_slots = min(self.transmission_attempts, 10)
                    self.backoff_time = random.uniform(0, 2 ** backoff_slots) * 0.1 
                    print(f"⏳ Backing off for {self.backoff_time:.2f} seconds...")
                    time.sleep(self.backoff_time)
                    sensing_attempts += 1
                    continue

                print("✅ Transmission completed successfully")
                self.is_transmitting = False
                self.collision_detected = False
                self.transmission_attempts = 0
                return True
            else:
                print("🔄 Channel busy, waiting...")
                time.sleep(0.5)
                sensing_attempts += 1

        print("❌ Channel persistently busy, transmission failed")
        return False

    def send_frame(self, data):
        """Send a frame with sequence number and wait for acknowledgment."""
        frame = {
            'sequence': self.sequence_number,
            'data': data,
            'crc': self.calculate_crc(data)
        }
        self.last_sent_time = time.time()
        self.sequence_number = (self.sequence_number + 1) % 2  # Toggle between 0 and 1
        return frame

    def receive_frame(self, frame):
        """Receive a frame and send acknowledgment."""
        if frame['sequence'] == self.expected_sequence:
            if self.check_crc(frame['data'], frame['crc']):
                self.expected_sequence = (self.expected_sequence + 1) % 2
                self.last_received_time = time.time()
                return True, frame['sequence']  # True for success, sequence number for ACK
            else:
                return False, None  # CRC check failed
        return False, None  # Wrong sequence number

    def check_timeout(self):
        """Check if acknowledgment timeout has occurred."""
        if time.time() - self.last_sent_time > self.timeout:
            return True
        return False


class TransportLayer:
    def __init__(self):
        self.port_table = {}  # Maps process names to port numbers
        self.process_table = {}  # Maps port numbers to process information
        self.well_known_ports = {
            'FTP': 21,
            'SSH': 22,
            'TELNET': 23,
            'SMTP': 25,
            'HTTP': 80,
            'POP3': 110,
            'HTTPS': 443
        }
        self.used_ports = set(self.well_known_ports.values())
        self.ephemeral_port_range = (49152, 65535)  # Dynamic/Private ports
        self.connections = {}  # Active connections
        self.window_size = 4  # Sliding window size
        self.sequence_number = 0
        self.ack_number = 0
        self.buffer = []
        self.ack_received = set()
        self.active_processes = {}  # Track active processes and their connections
        self.base = 0  # Base of the window
        self.next_seq_num = 0  # Next sequence number to be used
        self.last_cumulative_ack = -1  # Track last cumulative acknowledgment

    def create_segment(self, data, source_port, dest_port, seq_num):
        """Create a TCP segment with header and data."""
        # Get process information
        source_process = self.get_process_by_port(source_port)
        dest_process = self.get_process_by_port(dest_port)
        
        segment = {
            'source_port': source_port,
            'dest_port': dest_port,
            'source_process': source_process['name'] if source_process else 'unknown',
            'dest_process': dest_process['name'] if dest_process else 'unknown',
            'sequence': seq_num,
            'acknowledgment': 0,
            'data': data,
            'checksum': self.calculate_checksum(data) #calculate the checksum for the data
        }
        return segment

    def calculate_checksum(self, data):
        """Calculate checksum for error detection."""
        return hashlib.md5(data.encode()).hexdigest()

    def verify_checksum(self, segment):
        """Verify segment checksum."""
        calculated = self.calculate_checksum(segment['data'])
        return calculated == segment['checksum']

    def send_segments_gbn(self, data, source_port, dest_port):
        """Send data using Go-Back-N protocol."""
        segments = []
        data_size = len(data)
        chunk_size = 10  # Characters per segment
        
        # Get process information
        source_process = self.get_process_by_port(source_port) #get the process information for the source port
        dest_process = self.get_process_by_port(dest_port) #get the process information for the destination port
        
        print(f"\n📤 Sending data from {source_process['name']} to {dest_process['name']}")
        print(f"  Source Port: {source_port}")
        print(f"  Destination Port: {dest_port}")
        
        # Split data into chunks and create segments
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

    def receive_segments_gbn(self, segment):
        """Receive segments using Go-Back-N protocol."""
        if self.verify_checksum(segment):
            if segment['sequence'] == self.ack_number:
                print(f"✅ Received segment {segment['sequence']} successfully")
                self.ack_number = (self.ack_number + 1) % 8
                return True, segment['data']
            else:
                print(f"❌ Expected segment {self.ack_number}, got segment {segment['sequence']}")
                return False, None
        return False, None

    def handle_ack_gbn(self, ack_num):
        """Handle cumulative acknowledgment in Go-Back-N protocol."""
        if ack_num > self.last_cumulative_ack:
            print(f"📥 Received cumulative ACK {ack_num}")
            self.last_cumulative_ack = ack_num
            
            # Move window based on cumulative ACK
            while self.base <= ack_num:
                if self.base in self.ack_received:
                    self.ack_received.remove(self.base)
                self.base = (self.base + 1) % 8
                print(f"🔄 Window moved, new base: {self.base}")
            
            # Send more segments if window has space
            if self.base + self.window_size > self.next_seq_num:
                remaining_segments = len(self.buffer) - (self.next_seq_num - self.base)
                if remaining_segments > 0:
                    segments_to_send = min(remaining_segments, self.window_size - (self.next_seq_num - self.base))
                    for i in range(segments_to_send):
                        segment = self.buffer[self.next_seq_num - self.base + i]
                        print(f"📤 Sending additional segment {segment['sequence']}")
                        self.next_seq_num = (self.next_seq_num + 1) % 8

    def assign_port(self, process_name, is_well_known=False):
        """Assign a port number to a process."""
        # For well-known services, use their standard ports
        if is_well_known and process_name in self.well_known_ports:
            port = self.well_known_ports[process_name]
            self.port_table[process_name] = port
            self.process_table[port] = {
                'name': process_name,
                'type': 'well-known',
                'status': 'active',
                'connections': []
            }
            self.active_processes[process_name] = {
                'port': port,
                'type': 'well-known',
                'status': 'active'
            }
            return port
        
        # For all other services, use ephemeral ports
        while True:
            port = random.randint(*self.ephemeral_port_range)
            if port not in self.used_ports:
                self.used_ports.add(port)
                self.port_table[process_name] = port
                self.process_table[port] = {
                    'name': process_name,
                    'type': 'ephemeral',
                    'status': 'active',
                    'connections': []
                }
                self.active_processes[process_name] = {
                    'port': port,
                    'type': 'ephemeral',
                    'status': 'active'
                }
                print(f"📌 Assigned ephemeral port {port} to {process_name}")
                return port

    def establish_connection(self, source_process, dest_process):
        """Establish a connection between two processes."""
        source_port = self.get_port_by_process(source_process)
        dest_port = self.get_port_by_process(dest_process)
        
        if not source_port or not dest_port:
            print(f"❌ Cannot establish connection: One or both processes not found")
            return False
            
        # Create connection entry
        connection_id = f"{source_process}-{dest_process}"
        self.connections[connection_id] = {
            'source': source_process,
            'dest': dest_process,
            'source_port': source_port,
            'dest_port': dest_port,
            'status': 'established',
            'created_at': time.time() #create the connection and store the information 
        }
        
        # Update process tables
        self.process_table[source_port]['connections'].append(connection_id)
        self.process_table[dest_port]['connections'].append(connection_id)
        
        print(f"✅ Established connection between {source_process} (Port {source_port}) and {dest_process} (Port {dest_port})")
        return True

    def close_connection(self, source_process, dest_process):
        """Close a connection between two processes."""
        connection_id = f"{source_process}-{dest_process}"
        if connection_id in self.connections:
            # Update process tables
            source_port = self.connections[connection_id]['source_port']
            dest_port = self.connections[connection_id]['dest_port']
            
            if source_port in self.process_table:
                self.process_table[source_port]['connections'].remove(connection_id)
            if dest_port in self.process_table:
                self.process_table[dest_port]['connections'].remove(connection_id)
            
            # Remove connection
            del self.connections[connection_id]
            print(f"✅ Closed connection between {source_process} and {dest_process}")
            return True
        return False

    def show_process_table(self):
        """Display all processes and their port assignments."""
        print("\n📊 Process-Port Table:")
        print("\nWell-Known Services:")
        for service, port in self.well_known_ports.items():
            status = self.process_table.get(port, {}).get('status', 'inactive')
            connections = self.process_table.get(port, {}).get('connections', [])
            print(f"  {service}: Port {port} ({status})")
            if connections:
                print(f"    Active connections: {len(connections)}")
                for conn in connections:
                    print(f"    - {conn}")
        
        print("\nActive Ephemeral Processes:")
        for port, info in self.process_table.items():
            if info['type'] == 'ephemeral':
                connections = info.get('connections', [])
                print(f"  {info['name']}: Port {port} ({info['status']})")
                if connections:
                    print(f"    Active connections: {len(connections)}")
                    for conn in connections:
                        print(f"    - {conn}")

    def send_data_between_processes(self, source_process, dest_process, data):
        """Send data between two processes."""
        if source_process not in self.network or dest_process not in self.network:
            print("One or both devices do not exist!")
            return False
            
        print("\n=== Protocol Stack Demonstration ===")
        print("\n1. Application Layer (FTP):")
        print(f"📤 Sending data from {source_process} to {dest_process}")
        
        # Get port information
        source_port = self.get_port_by_process(source_process)
        dest_port = self.get_port_by_process(dest_process)
        print(f"  Source Port: {source_port}")
        print(f"  Destination Port: {dest_port}")
        
        print("\n2. Transport Layer (Go-Back-N):")
        segments = self.send_segments_gbn(data, source_port, dest_port)
        
        print("\n3. Network Layer (IP/Routing):")
        source_ip = self.ip_addresses.get(source_process)
        dest_ip = self.ip_addresses.get(dest_process)
        print(f"📡 Routing packet from {source_ip} to {dest_ip}")
        print(f"  Source Device: {source_process}")
        print(f"  Destination Device: {dest_process}")
        
        # Get next hop through router
        next_hop = self.route_packet(source_ip, dest_ip)
        if next_hop:
            print(f"  Next Hop: {next_hop}")
        
        print("\n4. Data Link Layer (MAC/ARP):")
        # Show ARP resolution
        source_mac = self.network.nodes[source_process]['data_link'].mac_address
        dest_mac = self.network.nodes[dest_process]['data_link'].mac_address
        print(f"  Source MAC: {source_mac}")
        print(f"  Destination MAC: {dest_mac}")
        
        print("\n5. Physical Layer:")
        print(f"  Data being transmitted through physical medium")
        
        print("\n=== Message Delivery Status ===")
        print(f"✅ Message successfully received at {dest_process}: {data}")
        print("==============================\n")
        
        return True

    def get_port_by_process(self, process_name):
        """Get port number for a process."""
        return self.port_table.get(process_name)

    def get_process_by_port(self, port):
        """Get process information for a port."""
        return self.process_table.get(port)


class TelnetClient:
    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.buffer = b""

    def read_until(self, expected, timeout=5):
        self.sock.settimeout(timeout)
        while expected not in self.buffer:
            data = self.sock.recv(4096)
            if not data:
                break
            self.buffer += data
        return self.buffer

    def write(self, data):
        self.sock.sendall(data)

    def close(self):
        self.sock.close()


class ApplicationLayer:
    def __init__(self):
        self.services = {
            'FTP': self.ftp_service,
            'TELNET': self.telnet_service
        }
        self.active_connections = {}

    def start_service(self, service_name, host, port, username=None, password=None):
        """Start an application service."""
        if service_name in self.services:
            return self.services[service_name](host, port, username, password)
        return None

    def ftp_service(self, host, port, username=None, password=None):
        """FTP service implementation."""
        try:
            # Create a mock FTP connection for simulation
            class MockFTP:
                def __init__(self, host, port):
                    self.host = host
                    self.port = port
                    self.connected = True
                    self.files = {}
                
                def connect(self, host, port):
                    self.host = host
                    self.port = port
                    self.connected = True
                
                def login(self, user=None, passwd=None):
                    if not self.connected:
                        raise Exception("Not connected")
                    return True
                
                def storbinary(self, cmd, fp):
                    if not self.connected:
                        raise Exception("Not connected")
                    filename = cmd.split()[-1]
                    self.files[filename] = fp.read()
                    return True
                
                def retrbinary(self, cmd, callback):
                    if not self.connected:
                        raise Exception("Not connected")
                    filename = cmd.split()[-1]
                    if filename in self.files:
                        callback(self.files[filename])
                        return True
                    return False
                
                def close(self):
                    self.connected = False
            
            ftp = MockFTP(host, port)
            ftp.connect(host, port)
            if username and password:
                ftp.login(username, password)
            else:
                ftp.login()
            return ftp
        except Exception as e:
            print(f"FTP Error: {str(e)}")
            return None

    def telnet_service(self, host, port, username=None, password=None):
        """Telnet service implementation (mock for simulation)."""
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

    def send_file_ftp(self, ftp_connection, local_file, remote_file):
        """Send a file using FTP."""
        try:
            with open(local_file, 'rb') as file:
                ftp_connection.storbinary(f'STOR {remote_file}', file)
            return True
        except Exception as e:
            print(f"FTP Send Error: {str(e)}")
            return False

    def receive_file_ftp(self, ftp_connection, remote_file, local_file):
        """Receive a file using FTP."""
        try:
            with open(local_file, 'wb') as file:
                ftp_connection.retrbinary(f'RETR {remote_file}', file.write)
            return True
        except Exception as e:
            print(f"FTP Receive Error: {str(e)}") 
            return False

    def send_command_telnet(self, telnet_connection, command):
        """Send a command using Telnet."""
        try:
            telnet_connection.write(command.encode('ascii') + b"\n")
            response = telnet_connection.read_until(b"$", timeout=5)
            return response.decode('ascii')
        except Exception as e:
            print(f"Telnet Command Error: {str(e)}")
            return None


class NetworkSimulator:
    def __init__(self):
        self.network = nx.Graph() 
        self.connections = {}
        self.data_log = []
        self.switch_tables = {}
        self.bridge_tables = {}
        self.ip_addresses = {}  # Store IP addresses for devices
        self.subnet_masks = {}  # Store subnet masks for devices
        self.arp_tables = {}    # Store ARP tables for devices
        self.routing_tables = {} # Store routing tables for routers
        self.broadcast_domains = 0
        self.collision_domains = 0
        self.transport_layer = TransportLayer()
        self.application_layer = ApplicationLayer()
        self.ip_prefixes = {}  # Store IP prefixes for LCP
        self.prefix_tree = {}  # Trie for LCP lookups
        self.arp_timeout = 300  # ARP cache timeout in seconds
        self.arp_timestamps = {} # Track when ARP entries were added

    def add_device(self, name):
        """Adds an end device with data link layer."""
        self.network.add_node(name, type=DeviceType.END_DEVICE, data_link=DataLinkLayer())
        self.connections[name] = []
        print(f"Added device: {name} (MAC: {self.network.nodes[name]['data_link'].mac_address})")

    def add_hub(self, name):
        """Adds a hub."""
        self.network.add_node(name, type=DeviceType.HUB)
        self.connections[name] = []
        print(f"Added hub: {name}")

    def add_bridge(self, name):
        """Adds a bridge with MAC learning capability."""
        self.network.add_node(name, type=DeviceType.BRIDGE)
        self.connections[name] = []
        self.bridge_tables[name] = {}
        print(f"Added bridge: {name}")

    def add_switch(self, name):
        """Adds a switch with MAC learning capability."""
        self.network.add_node(name, type=DeviceType.SWITCH)
        self.connections[name] = []
        self.switch_tables[name] = {}
        print(f"Added switch: {name}")

    def add_router(self, name):
        if name in self.network:
            print(f"Router {name} already exists!")
            return
        self.network.add_node(name, type=DeviceType.ROUTER, data_link=DataLinkLayer())
        self.connections[name] = []
        # Initialize routing table and ARP tables
        self.routing_tables[name] = []
        self.arp_tables[name] = {}
        self.arp_timestamps[name] = {}  # Initialize ARP timestamps
        print(f"🛣️ Router {name} added to the network.")

    def connect(self, node1, node2):
        """Connects two nodes and updates connection storage."""
        if node1 in self.network and node2 in self.network:
            self.network.add_edge(node1, node2)
            self.connections[node1].append(node2)
            self.connections[node2].append(node1)
            
            # Initialize ARP tables if they don't exist
            if node1 not in self.arp_tables:
                self.arp_tables[node1] = {}
                self.arp_timestamps[node1] = {}
            if node2 not in self.arp_tables:
                self.arp_tables[node2] = {}
                self.arp_timestamps[node2] = {}
            
            # Update ARP tables for connected devices
            if 'data_link' in self.network.nodes[node1] and 'data_link' in self.network.nodes[node2]:
                mac1 = self.network.nodes[node1]['data_link'].mac_address
                mac2 = self.network.nodes[node2]['data_link'].mac_address
                
                # Update ARP tables if IP addresses exist
                if node1 in self.ip_addresses:
                    self.update_arp_table(node2, self.ip_addresses[node1], mac1)
                if node2 in self.ip_addresses:
                    self.update_arp_table(node1, self.ip_addresses[node2], mac2)
                
                # If either node is a router, initialize its routing table
                if self.network.nodes[node1]['type'] == DeviceType.ROUTER:
                    self.initialize_router_table(node1)
                if self.network.nodes[node2]['type'] == DeviceType.ROUTER:
                    self.initialize_router_table(node2)
            
            print(f"Connected {node1} to {node2}")
        else:
            print("One or both nodes do not exist!")

    def learn_mac_address(self, device_name, mac_address, port):
        """Learn MAC address for switches and bridges."""
        node_type = self.network.nodes[device_name]['type'] #automatically build the mac table for the device   
        if node_type == DeviceType.SWITCH:
            self.switch_tables[device_name][mac_address] = port
        elif node_type == DeviceType.BRIDGE:
            self.bridge_tables[device_name][mac_address] = port

    def send_data(self, sender, receiver, message):
        """Sends data with enhanced data link layer features."""
        if sender not in self.network or receiver not in self.network:
            print("One or both nodes do not exist!")
            return

        # Update ARP tables for both sender and receiver
        sender_ip = self.ip_addresses.get(sender)
        receiver_ip = self.ip_addresses.get(receiver)
        
        if sender_ip and receiver_ip:
            # Get MAC addresses
            sender_mac = self.network.nodes[sender]['data_link'].mac_address
            receiver_mac = self.network.nodes[receiver]['data_link'].mac_address
            
            # Update ARP tables
            self.update_arp_table(sender, receiver_ip, receiver_mac)
            self.update_arp_table(receiver, sender_ip, sender_mac)

        sender_node = self.network.nodes[sender]
        sender_dl = sender_node.get('data_link')

        if not sender_dl:
            print(f"Error: {sender} does not have data link layer!")
            return

        # Reset transmission attempts and cumulative ACK
        sender_dl.transmission_attempts = 0
        sender_dl.last_cumulative_ack = -1

        # Split message into smaller frames (simulating MTU)
        frame_size = 10  # characters per frame
        message_parts = [message[i:i+frame_size] for i in range(0, len(message), frame_size)]
        
        print(f"\n📡 Attempting transmission from {sender} to {receiver} using Go-Back-N with cumulative ACK...")
        print(f"Message split into {len(message_parts)} frames")

        # First, try to access the channel using CSMA/CD
        if not sender_dl.csma_cd():
            print("❌ Failed to access channel")
            return

        # Send initial window of frames using Go-Back-N
        frames = sender_dl.send_frames_gbn(message_parts)
        
        # Start from sender and traverse through the network
        path = self.find_path(sender, receiver)
        if not path:
            print(f"⚠️ No path found from {sender} to {receiver}")
            return

        # Now, you can process the path as needed, e.g.:
        for i in range(1, len(path)):
            current_node = path[i-1]
            next_node = path[i]
            node_type = self.network.nodes[current_node]['type']

            if node_type in [DeviceType.SWITCH, DeviceType.BRIDGE]:
                # Learn MAC addresses of all connected devices
                for neighbor in self.connections[current_node]:
                    if neighbor in self.network.nodes and self.network.nodes[neighbor].get('data_link'):
                        neighbor_dl = self.network.nodes[neighbor]['data_link']
                        self.learn_mac_address(current_node, neighbor_dl.mac_address, neighbor)

                # Get appropriate MAC table
                mac_table = (self.switch_tables[current_node]
                           if node_type == DeviceType.SWITCH
                           else self.bridge_tables[current_node])
                if next_node in mac_table:
                    print(f"Forwarding through {current_node} to port {next_node}")
                else:
                    print(f"Flooding through {current_node} to {next_node}")
            # No else block for hubs/end devices, just follow the path

            # Process frames at receiver (only at the last hop)
            if i == len(path) - 1:
                if next_node in self.network.nodes and self.network.nodes[next_node].get('data_link'):
                    receiver_dl = self.network.nodes[next_node]['data_link']
                    received_data = []
                    last_successful_seq = -1

                    for frame in frames:
                        success, ack_seq = receiver_dl.receive_frame_gbn(frame)
                        if success:
                            received_data.append(frame['data'])
                            last_successful_seq = frame['sequence']
                            print(f"📤 {next_node} sending cumulative ACK {last_successful_seq}")
                            sender_dl.handle_ack_gbn(last_successful_seq)
                        else:
                            print(f"❌ Frame {frame['sequence']} failed at {next_node}")
                            break

                    if received_data:
                        complete_message = ''.join(received_data)
                        print(f"\n✅ Message successfully received at {next_node}: {complete_message}")
                        self.data_log.append((sender, next_node, len(message.encode())))
                    else:
                        print(f"\n❌ No frames were successfully received at {next_node}")
                else:
                    print(f"⚠️ Receiver {next_node} does not have data link layer!")

    def hub_broadcast(self, sender, hub, message):
        """Hub receives data and forwards it to all connected devices."""
        if hub in self.network and self.network.nodes[hub]['type'] == DeviceType.HUB:
            data_size = len(message.encode())
            print(f"📡 {sender} sent {data_size} bytes to Hub {hub}: {message}")

            for device in self.connections.get(hub, []):
                if device != sender:
                    self.send_data(hub, device, message)
        else:
            print(f"⚠️ {hub} is not a valid hub!")

    def visualize(self):
        """Draws the network topology with different colors for different device types."""
        pos = nx.spring_layout(self.network)
        labels = {
            node: f"{node}\n{self.network.nodes[node]['data_link'].mac_address if 'data_link' in self.network.nodes[node] else ''}"
            for node in self.network.nodes()}

        node_colors = []
        for node in self.network.nodes():
            node_type = self.network.nodes[node]['type']
            if node_type == DeviceType.HUB:
                node_colors.append('red')
            elif node_type == DeviceType.BRIDGE:
                node_colors.append('green')
            elif node_type == DeviceType.SWITCH:
                node_colors.append('yellow')
            else:
                node_colors.append('blue')

        nx.draw(self.network, pos, labels=labels, with_labels=True,
                node_color=node_colors, edge_color='gray')
        plt.show()

    def show_data_log(self):
        """Displays the log of all data transfers."""
        print("\n📊 Data Transfer Log:")
        total_data = 0
        for log in self.data_log:
            sender, receiver, size = log
            print(f"📡 {sender} → {receiver} | {size} bytes")
            total_data += size
        print(f"\n📈 Total Data Transferred: {total_data} bytes")

    def connect_all_to_device(self, central_device):
        """Connects all end devices to a specified switch or hub."""
        if central_device not in self.network:
            print(f"⚠️ {central_device} does not exist!")
            return

        central_type = self.network.nodes[central_device]['type']
        if central_type not in [DeviceType.HUB, DeviceType.SWITCH]:
            print(f"⚠️ {central_device} must be a hub or switch!")
            return

        # Find all end devices
        end_devices = [node for node in self.network.nodes()
                       if self.network.nodes[node]['type'] == DeviceType.END_DEVICE]

        if not end_devices:
            print("⚠️ No end devices found in the network!")
            return

        # Connect each end device to the central device
        connected_count = 0
        for device in end_devices:
            if device not in self.connections[central_device]:
                self.connect(device, central_device)
                connected_count += 1

        print(f"✅ Connected {connected_count} devices to {central_device}")

    def create_star_topology(self, num_devices, central_type="switch"):
        """Creates a star topology with specified number of devices."""
        if num_devices < 1:
            print("Number of devices must be at least 1!")
            return

        # Clear existing network
        self.network = nx.Graph()
        self.connections = {}
        self.data_log = []
        self.switch_tables = {}
        self.bridge_tables = {}

        # Create central device
        central_name = "Central" + central_type.capitalize()
        if central_type.lower() == "switch":
            self.add_switch(central_name)
        else:
            self.add_hub(central_name)

        # Create end devices
        for i in range(num_devices):
            device_name = f"Device{i + 1}"
            self.add_device(device_name)
            self.connect(device_name, central_name)

        # Calculate domains
        self.calculate_domains()
        print(f"\n✅ Created star topology with {num_devices} devices and {central_name}")
        print(f"📊 Network Statistics:")
        print(f"   - Broadcast Domains: {self.broadcast_domains}")
        print(f"   - Collision Domains: {self.collision_domains}")

    def calculate_domains(self):
        """Calculate number of broadcast and collision domains."""
        # Reset counters
        self.broadcast_domains = 0
        self.collision_domains = 0

        # Count broadcast domains (one per switch/bridge)
        for node in self.network.nodes():
            node_type = self.network.nodes[node]['type']
            if node_type in [DeviceType.SWITCH, DeviceType.BRIDGE]:
                self.broadcast_domains += 1

        # Count collision domains
        # Each hub creates a new collision domain
        # Each switch port is a separate collision domain
        for node in self.network.nodes():
            node_type = self.network.nodes[node]['type']
            if node_type == DeviceType.HUB:
                self.collision_domains += 1
            elif node_type == DeviceType.SWITCH:
                # Each port on a switch is a separate collision domain
                self.collision_domains += len(self.connections[node])

        # If no switches or hubs, there's one broadcast domain
        if self.broadcast_domains == 0:
            self.broadcast_domains = 1

    def show_mac_tables(self):
        """Displays the MAC address tables for switches and bridges."""
        print("\n📊 MAC Address Tables:")

        # Show switch tables
        if self.switch_tables:
            print("\n🔌 Switch MAC Tables:")
            for switch, table in self.switch_tables.items():
                print(f"\n{switch}:")
                if table:
                    for mac, port in table.items():
                        print(f"  MAC: {mac} → Port: {port}")
                else:
                    print("  No entries")

        # Show bridge tables
        if self.bridge_tables:
            print("\n🌉 Bridge MAC Tables:")
            for bridge, table in self.bridge_tables.items():
                print(f"\n{bridge}:")
                if table:
                    for mac, port in table.items():
                        print(f"  MAC: {mac} → Port: {port}")
                else:
                    print("  No entries")

        if not self.switch_tables and not self.bridge_tables:
            print("No MAC address tables available.")

    def assign_ip(self, device_name, ip_with_mask):
        """Assign IP address to device and update ARP tables."""
        try:
            # First check if device exists
            if device_name not in self.network:
                print(f"❌ Device {device_name} does not exist!")
                return
                
            # Parse IP address and mask
            try:
                ip_interface = ipaddress.ip_interface(ip_with_mask)
            except ValueError as e:
                print(f"❌ Invalid IP address format: {e}")
                return
                
            # Store IP and mask
            self.ip_addresses[device_name] = str(ip_interface.ip)
            self.subnet_masks[device_name] = str(ip_interface.netmask)
            
            # Initialize ARP table if it doesn't exist
            if device_name not in self.arp_tables:
                self.arp_tables[device_name] = {}
                self.arp_timestamps[device_name] = {}
            
            # Update ARP tables for connected devices
            device_mac = None
            if 'data_link' in self.network.nodes[device_name]:
                device_mac = self.network.nodes[device_name]['data_link'].mac_address
            
            # Update ARP tables for all connected devices
            for neighbor in self.connections.get(device_name, []):
                if neighbor in self.network.nodes:
                    # Update ARP table for both devices
                    if device_mac:
                        self.update_arp_table(neighbor, str(ip_interface.ip), device_mac)
                    
                    # If neighbor has a data link layer, update its ARP table
                    if 'data_link' in self.network.nodes[neighbor]:
                        neighbor_mac = self.network.nodes[neighbor]['data_link'].mac_address
                        if neighbor in self.ip_addresses:
                            self.update_arp_table(device_name, self.ip_addresses[neighbor], neighbor_mac)
                    
                    # If either device is a router, initialize its routing table
                    if self.network.nodes[device_name]['type'] == DeviceType.ROUTER:
                        self.initialize_router_table(device_name)
                    if self.network.nodes[neighbor]['type'] == DeviceType.ROUTER:
                        self.initialize_router_table(neighbor)
            
            # Add IP prefix information
            self.ip_prefixes[device_name] = {
                'network': str(ip_interface.network),
                'prefix_len': ip_interface.network.prefixlen,
                'ip': str(ip_interface.ip)
            }
            
            print(f"✅ Assigned IP {ip_interface} to {device_name}")
            
        except Exception as e:
            print(f"❌ Error assigning IP address: {str(e)}")

    def show_ip_config(self, device_name):
        ip = self.ip_addresses.get(device_name, None)
        mask = self.subnet_masks.get(device_name, None)
        if ip and mask:
            print(f"{device_name}: IP {ip}, Subnet Mask {mask}")
        else:
            print(f"{device_name} has no IP configuration.")

    def initialize_router_table(self, router):
        """Initialize routing table for a router."""
        if router not in self.routing_tables:
            self.routing_tables[router] = []
            
        # Clear existing routes
        self.routing_tables[router] = []
        
        # Add routes for directly connected devices
        for neighbor in self.connections[router]:
            if neighbor in self.ip_addresses:
                # Get IP prefix information
                neighbor_ip = self.ip_addresses[neighbor]
                neighbor_mask = self.subnet_masks[neighbor]
                ip_interface = ipaddress.ip_interface(f"{neighbor_ip}/{neighbor_mask}")
                network = str(ip_interface.network)
                prefix_len = ip_interface.network.prefixlen
                
                # Calculate LCP length
                lcp_length = self._calculate_lcp_length(network, str(ip_interface.network))
                
                # Add route with LCP information
                self.routing_tables[router].append({
                    'destination': neighbor,
                    'next_hop': neighbor,
                    'hop_count': 1,
                    'prefix': network,
                    'prefix_len': prefix_len,
                    'lcp_length': lcp_length
                })
                
                # Update IP prefix information
                self.ip_prefixes[neighbor] = {
                    'network': network,
                    'prefix_len': prefix_len,
                    'ip': str(ip_interface.ip)
                }
                
                print(f"✅ Added route to {neighbor} in {router}'s routing table")
        
        print(f"Initialized routing table for {router}")

    def rip_update(self, router):
        # Send this router's table to all neighbors that are routers
        updated = False
        my_table = self.routing_tables[router]
        for neighbor in self.connections[router]:
            if self.network.nodes[neighbor]['type'] == DeviceType.ROUTER:
                neighbor_table = self.routing_tables[neighbor]
                # Build a map for quick lookup
                neighbor_map = {entry['destination']: entry for entry in neighbor_table}
                for entry in my_table:
                    dest = entry['destination']
                    if dest == neighbor:
                        continue  # Don't advertise route to neighbor itself
                    new_hop_count = entry['hop_count'] + 1
                    #if the destination is not in the neighbor_map , add it.
                

                    if dest not in neighbor_map:
                        neighbor_table.append({
                            'destination': dest,
                            'next_hop': router,
                            'hop_count': new_hop_count
                        })
                        updated = True
                    else:
                        # Update if new hop count is smaller OR equal (same hop count)
                        if new_hop_count <= neighbor_map[dest]['hop_count']:
                            neighbor_map[dest]['hop_count'] = new_hop_count
                            neighbor_map[dest]['next_hop'] = router
                            updated = True
        return updated

    def rip_update_all(self):
        # Initialize all router tables with direct neighbors
        for router in self.network.nodes:
            if self.network.nodes[router]['type'] == DeviceType.ROUTER:
                self.initialize_router_table(router)
        # Run RIP updates until convergence
        print("\n🔄 Running RIP updates...")
        changed = True
        rounds = 0
        while changed and rounds < 16: #infinity count
            changed = False
            for router in self.network.nodes:
                if self.network.nodes[router]['type'] == DeviceType.ROUTER:
                    if self.rip_update(router):
                        changed = True
            rounds += 1
        print(f"RIP converged in {rounds} rounds.")

    def print_routing_tables(self):
        print("\n📚 Routing Tables (RIP):")
        for router in self.routing_tables:
            print(f"\nRouter {router}:")
            table = self.routing_tables[router]
            if not table:
                print("  (empty)")
            else:
                for entry in table:
                    print(f"  Dest: {entry['destination']}, Next Hop: {entry['next_hop']}, Hops: {entry['hop_count']}")

    def start_application_service(self, service_name, device_name, host, port, username=None, password=None):
        """Start an application service on a device."""
        if device_name not in self.network:
            print(f"Device {device_name} does not exist!")
            return None

        # Check if it's a well-known service
        is_well_known = service_name.upper() in self.transport_layer.well_known_ports
        
        # Assign port for the service
        port_num = self.transport_layer.assign_port(service_name, is_well_known)
        print(f"Starting {service_name} service on {device_name} (Port: {port_num})")
        
        # Start the service
        service = self.application_layer.start_service(service_name, host, port, username, password)
        if service:
            self.application_layer.active_connections[device_name] = {
                'service': service,
                'type': service_name,
                'port': port_num,
                'process': self.transport_layer.get_process_by_port(port_num)
            }
            return service
        return None

    def send_file(self, sender, receiver, local_file, remote_file):
        """Send a file between devices using FTP."""
        if sender not in self.application_layer.active_connections:
            print(f"No active service on {sender}")
            return False

        connection = self.application_layer.active_connections[sender]
        if connection['type'] != 'FTP':
            print(f"{sender} does not have an active FTP service")
            return False

        # Use transport layer to send the file
        with open(local_file, 'rb') as file:
            data = file.read()
            segments = self.transport_layer.send_segments_gbn(
                data.decode(),
                connection['port'],
                self.transport_layer.well_known_ports['FTP']
            )

            # Send segments through the network
            for segment in segments:
                self.send_data(sender, receiver, segment['data'])

        return True

    def execute_command(self, device_name, command):
        """Execute a command on a device using Telnet."""
        if device_name not in self.application_layer.active_connections:
            print(f"No active service on {device_name}")
            return None

        connection = self.application_layer.active_connections[device_name]
        if connection['type'] != 'TELNET':
            print(f"{device_name} does not have an active Telnet service")
            return None

        return self.application_layer.send_command_telnet(connection['service'], command)

    def add_ip_prefix(self, device_name, ip_with_mask):
        """Add IP prefix to the LCP trie."""
        try:
            ip_interface = ipaddress.ip_interface(ip_with_mask)
            network = str(ip_interface.network)
            prefix_len = ip_interface.network.prefixlen
            
            # Store the prefix
            self.ip_prefixes[device_name] = {
                'network': network,
                'prefix_len': prefix_len,
                'ip': str(ip_interface.ip)
            }
            
            # Add to trie
            self._add_to_trie(network, device_name)
            print(f"✅ Added IP prefix {network}/{prefix_len} to {device_name}")
        except Exception as e:
            print(f"❌ Invalid IP prefix: {e}")

    def _add_to_trie(self, prefix, device_name):
        """Add IP prefix to the trie structure."""
        current = self.prefix_tree
        for bit in prefix.split('.'):
            if bit not in current:
                current[bit] = {}
            current = current[bit]
        current['device'] = device_name

    def find_longest_common_prefix(self, ip_address):
        """Find the longest common prefix match for an IP address."""
        try:
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
        except Exception as e:
            print(f"❌ Error finding LCP: {e}")
            return None

    def show_ip_prefixes(self):
        """Display all IP prefixes and their LCP information."""
        print("\n📊 IP Prefixes and LCP Information:")
        for device, prefix_info in self.ip_prefixes.items():
            print(f"\n{device}:")
            print(f"  Network: {prefix_info['network']}")
            print(f"  Prefix Length: {prefix_info['prefix_len']}")
            print(f"  IP Address: {prefix_info['ip']}")

    def route_packet(self, source_ip, dest_ip):
        """Route a packet using LCP matching and ARP resolution."""
        source_device = self.find_longest_common_prefix(source_ip)
        dest_device = self.find_longest_common_prefix(dest_ip)
        
        if not source_device or not dest_device:
            print(f"❌ No route found for {source_ip} -> {dest_ip}")
            return None
            
        print(f"📡 Routing packet from {source_ip} to {dest_ip}")
        print(f"  Source Device: {source_device}")
        print(f"  Destination Device: {dest_device}")
        
        # Get MAC address for next hop
        next_hop = None
        if dest_device in self.routing_tables.get(source_device, []):
            # Get all routes to destination
            routes = [r for r in self.routing_tables[source_device] 
                     if r['destination'] == dest_device]
            
            if routes:
                # Sort by LCP length and hop count
                best_route = max(routes, 
                               key=lambda x: (x.get('lcp_length', 0), -x['hop_count']))
                next_hop = best_route['next_hop']
                
                if next_hop:
                    # Resolve MAC address for next hop
                    mac_address = self.get_mac_address(source_device, next_hop)
                    if mac_address:
                        print(f"  Next Hop: {next_hop} (MAC: {mac_address})")
                        print(f"  Route selected with LCP length: {best_route.get('lcp_length', 'N/A')}")
                        return next_hop
                    else:
                        print(f"❌ Could not resolve MAC address for {next_hop}")
        
        return None

    def update_routing_table_lcp(self, router):
        """Update routing table based on LCP matches."""
        if router not in self.routing_tables:
            self.routing_tables[router] = []
        
        # Get router's own prefix
        router_prefix = self.ip_prefixes.get(router)
        if not router_prefix:
            print(f"❌ No IP prefix found for {router}")
            return False

        updated = False
        for device, prefix_info in self.ip_prefixes.items():
            if device == router:
                continue

            # Check if the device's network is reachable through this router
            if self._is_reachable(router_prefix['network'], prefix_info['network']):
                # Calculate LCP match length
                lcp_length = self._calculate_lcp_length(router_prefix['network'], prefix_info['network'])
                
                # Find or create route entry
                route_entry = next((r for r in self.routing_tables[router] 
                                  if r['destination'] == device), None)
                
                if not route_entry:
                    # Add new route with LCP information
                    self.routing_tables[router].append({
                        'destination': device,
                        'next_hop': self._find_next_hop(router, device),
                        'hop_count': 1,
                        'prefix': prefix_info['network'],
                        'prefix_len': prefix_info['prefix_len'],
                        'lcp_length': lcp_length
                    })
                    updated = True
                    print(f"✅ Added route to {device} with LCP length {lcp_length}")
                else:
                    # Update existing route if LCP length is better
                    if lcp_length > route_entry.get('lcp_length', 0):
                        route_entry['prefix'] = prefix_info['network']
                        route_entry['prefix_len'] = prefix_info['prefix_len']
                        route_entry['lcp_length'] = lcp_length
                        route_entry['next_hop'] = self._find_next_hop(router, device)
                        updated = True
                        print(f"✅ Updated route to {device} with better LCP length {lcp_length}")

        return updated

    def _calculate_lcp_length(self, prefix1, prefix2):
        """Calculate the length of the longest common prefix between two networks."""
        try:
            # Always use the network address of the network, not the host address
            net1 = ipaddress.ip_network(prefix1, strict=False)
            net2 = ipaddress.ip_network(prefix2, strict=False)
            addr1 = bin(int(net1.network_address))[2:].zfill(32)
            addr2 = bin(int(net2.network_address))[2:].zfill(32)
            lcp_length = 0
            for b1, b2 in zip(addr1, addr2):
                if b1 == b2:
                    lcp_length += 1
                else:
                    break
            return lcp_length
        except Exception as e:
            print(f"❌ Error calculating LCP length: {e}")
            return 0

    def _is_reachable(self, source_network, dest_network):
        """Check if destination network is reachable from source network."""
        try:
            source = ipaddress.ip_network(source_network)
            dest = ipaddress.ip_network(dest_network)
            
            # Calculate LCP length
            lcp_length = self._calculate_lcp_length(source_network, dest_network)
            
            # Consider networks reachable if they share a significant prefix
            return lcp_length >= 16  # At least /16 network match
        except Exception as e:
            print(f"❌ Error checking reachability: {e}")
            return False

    def print_routing_tables(self):
        """Display routing tables with LCP information."""
        print("\n📚 Routing Tables (RIP with LCP):")
        for router in self.routing_tables:
            print(f"\nRouter {router}:")
            table = self.routing_tables[router]
            if not table:
                print("  (empty)")
            else:
                # Sort routes by LCP length (descending)
                sorted_routes = sorted(table, key=lambda x: x.get('lcp_length', 0), reverse=True)
                for entry in sorted_routes:
                    prefix_info = f" (Prefix: {entry.get('prefix', 'N/A')}/{entry.get('prefix_len', 'N/A')})"
                    lcp_info = f" [LCP: {entry.get('lcp_length', 'N/A')}]"
                    print(f"  Dest: {entry['destination']}, Next Hop: {entry['next_hop']}, "
                          f"Hops: {entry['hop_count']}{prefix_info}{lcp_info}")

    def update_arp_table(self, device_name, ip_address, mac_address):
        """Update ARP table for a device."""
        if device_name not in self.arp_tables:
            self.arp_tables[device_name] = {}
            self.arp_timestamps[device_name] = {}
        
        self.arp_tables[device_name][ip_address] = mac_address
        self.arp_timestamps[device_name][ip_address] = time.time()
        print(f"✅ Updated ARP table for {device_name}: {ip_address} -> {mac_address}")

    def get_mac_address(self, device_name, ip_address):
        """Get MAC address from ARP table or perform ARP request."""
        if device_name not in self.arp_tables:
            return None

        # Check if entry exists and is not expired
        if ip_address in self.arp_tables[device_name]:
            timestamp = self.arp_timestamps[device_name].get(ip_address, 0)
            if time.time() - timestamp < self.arp_timeout:
                return self.arp_tables[device_name][ip_address]
            else:
                # Remove expired entry
                del self.arp_tables[device_name][ip_address]
                del self.arp_timestamps[device_name][ip_address]

        # Perform ARP request
        return self._perform_arp_request(device_name, ip_address)

    def _perform_arp_request(self, device_name, target_ip):
        """Simulate ARP request to find MAC address."""
        print(f"🔍 {device_name} performing ARP request for {target_ip}")
        
        # Check if target IP belongs to any device
        for device, prefix_info in self.ip_prefixes.items():
            if device == device_name:
                continue
                
            try:
                target_network = ipaddress.ip_network(prefix_info['network'])
                if ipaddress.ip_address(target_ip) in target_network:
                    # Found the device, get its MAC address
                    if device in self.network.nodes and 'data_link' in self.network.nodes[device]:
                        mac = self.network.nodes[device]['data_link'].mac_address
                        self.update_arp_table(device_name, target_ip, mac)
                        
                        # Update ARP table for the target device as well
                        if device_name in self.ip_addresses:
                            device_mac = self.network.nodes[device_name]['data_link'].mac_address
                            self.update_arp_table(device, self.ip_addresses[device_name], device_mac)
                        
                        return mac
            except Exception as e:
                print(f"❌ Error in ARP request: {e}")
        
        print(f"❌ No MAC address found for {target_ip}")
        return None

    def show_arp_tables(self):
        """Display ARP tables for all devices."""
        print("\n📊 ARP Tables:")
        for device, arp_table in self.arp_tables.items():
            print(f"\n{device}:")
            if not arp_table:
                print("  (empty)")
            else:
                for ip, mac in arp_table.items():
                    age = int(time.time() - self.arp_timestamps[device][ip])
                    print(f"  IP: {ip} -> MAC: {mac} (Age: {age}s)")

    def clear_arp_tables(self):
        """Clear all ARP tables."""
        self.arp_tables.clear()
        self.arp_timestamps.clear()
        print("✅ ARP tables cleared")

    def establish_process_connection(self, source_device, dest_device, source_process, dest_process):
        """Establish a connection between processes on different devices."""
        if source_device not in self.network or dest_device not in self.network:
            print("One or both devices do not exist!")
            return False
            
        return self.transport_layer.establish_connection(source_process, dest_process)

    def close_process_connection(self, source_device, dest_device, source_process, dest_process):
        """Close a connection between processes."""
        if source_device not in self.network or dest_device not in self.network:
            print("One or both devices do not exist!")
            return False
            
        return self.transport_layer.close_connection(source_process, dest_process)

    def send_data_between_processes(self, source_device, dest_device, source_process, dest_process, data):
        """Send data between processes on different devices."""
        if source_device not in self.network or dest_device not in self.network:
            print("One or both devices do not exist!")
            return False
            
        print("\n=== Protocol Stack Demonstration ===")
        print("\n1. Application Layer (FTP):")
        print(f"📤 Sending data from {source_process} to {dest_process}")
        
        # Get port information
        source_port = self.transport_layer.get_port_by_process(source_process)
        dest_port = self.transport_layer.well_known_ports.get(dest_process, 21)
        print(f"  Source Port: {source_port}")
        print(f"  Destination Port: {dest_port}")
        
        print("\n2. Transport Layer (Go-Back-N):")
        segments = self.transport_layer.send_segments_gbn(data, source_port, dest_port)
        
        print("\n3. Network Layer (IP/Routing):")
        source_ip = self.ip_addresses.get(source_device)
        dest_ip = self.ip_addresses.get(dest_device)
        print(f"📡 Routing packet from {source_ip} to {dest_ip}")
        print(f"  Source Device: {source_device}")
        print(f"  Destination Device: {dest_device}")
        
        # Get next hop through router
        next_hop = self.route_packet(source_ip, dest_ip)
        if next_hop:
            print(f"  Next Hop: {next_hop}")
        
        print("\n4. Data Link Layer (MAC/ARP):")
        # Show ARP resolution
        source_mac = self.network.nodes[source_device]['data_link'].mac_address
        dest_mac = self.network.nodes[dest_device]['data_link'].mac_address
        print(f"  Source MAC: {source_mac}")
        print(f"  Destination MAC: {dest_mac}")
        
        print("\n5. Physical Layer:")
        print(f"  Data being transmitted through physical medium")
        
        print("\n=== Message Delivery Status ===")
        print(f"✅ Message successfully received at {dest_device}: {data}")
        print("==============================\n")
        
        return True

    def _find_next_hop(self, router, destination):
        """Find the next hop for a route."""
        if router not in self.connections:
            return None
            
        # First check direct connections
        if destination in self.connections[router]:
            return destination
            
        # Then check routing table
        if router in self.routing_tables:
            for route in self.routing_tables[router]:
                if route['destination'] == destination:
                    return route['next_hop']
                    
        return None

    def find_path(self, start, end):
        queue = deque([[start]])
        visited = set()
        while queue:
            path = queue.popleft()
            node = path[-1]
            if node == end:
                return path
            if node not in visited:
                visited.add(node)
                for neighbor in self.connections.get(node, []):
                    if neighbor not in visited:
                        new_path = list(path)
                        new_path.append(neighbor)
                        queue.append(new_path)
        return None


# ==========================
# 🚀 Interactive Network Simulator
# ==========================
def print_menu():
    print("\n=== Network Simulator Menu ===")
    print("1. Add a device")
    print("2. Add a hub")
    print("3. Add a bridge")
    print("4. Add a switch")
    print("5. Add a router")
    print("6. Connect nodes")
    print("7. Connect all devices to hub/switch")
    print("8. Create star topology")
    print("9. Send data between devices")
    print("10. Broadcast message through hub")
    print("11. Show network topology")
    print("12. Show data transfer log")
    print("13. Show network statistics")
    print("14. Show MAC address tables")
    print("15. Assign IP address to device")
    print("16. Show device IP configuration")
    print("17. Clear network")
    print("18. Run RIP dynamic routing update")
    print("19. Show all router RIP tables")
    print("20. Start Application Service")
    print("21. Send File")
    print("22. Execute Command")
    print("23. Add IP Prefix")
    print("24. Show IP Prefixes")
    print("25. Route Packet using LCP")
    print("26. Update Routing Tables with LCP")
    print("27. Show ARP Tables")
    print("28. Clear ARP Tables")
    print("29. Show Process-Port Table")
    print("30. Establish Process Connection")
    print("31. Close Process Connection")
    print("32. Send Data Between Processes")
    print("0. Exit")
    print("===========================")


def get_node_type():
    print("\nSelect node type:")
    print("1. End Device")
    print("2. Hub")
    print("3. Bridge")
    print("4. Switch")
    print("5. Router")
    while True:
        try:
            choice = int(input("Enter your choice (1-5): "))
            if 1 <= choice <= 5:
                return choice
            print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a valid number.")


def main():
    sim = NetworkSimulator()
    print_menu()
    
    while True:
        try:
            cmd = input("\nEnter command (number and arguments): ")
            if not cmd.strip():
                continue
                
            parts = cmd.split()
            choice = int(parts[0])
            args = parts[1:]

            if choice == 0:
                print("Exiting Network Simulator...")
                break
            elif choice == 1:
                if len(args) < 1:
                    print("Device name required.")
                else:
                    sim.add_device(args[0])
            elif choice == 2:
                if len(args) < 1:
                    print("Hub name required.")
                else:
                    sim.add_hub(args[0])
            elif choice == 3:
                if len(args) < 1:
                    print("Bridge name required.")
                else:
                    sim.add_bridge(args[0])
            elif choice == 4:
                if len(args) < 1:
                    print("Switch name required.")
                else:
                    sim.add_switch(args[0])
            elif choice == 5:
                if len(args) < 1:
                    print("Router name required.")
                else:
                    sim.add_router(args[0])
            elif choice == 6:
                if len(args) < 2:
                    print("Two node names required.")
                else:
                    sim.connect(args[0], args[1])
            elif choice == 15:
                if len(args) < 2:
                    print("Device name and IP/mask required.")
                else:
                    sim.assign_ip(args[0], args[1])
            elif choice == 20:
                if len(args) < 4:
                    print("Service name, device name, host, and port required.")
                else:
                    service_name = args[0].upper()
                    device_name = args[1]
                    host = args[2]
                    port = int(args[3])
                    sim.start_application_service(service_name, device_name, host, port)
            elif choice == 30:
                if len(args) < 4:
                    print("Source device, destination device, source process, and destination process required.")
                else:
                    sim.establish_process_connection(args[0], args[1], args[2], args[3])
            elif choice == 32:
                if len(args) < 5:
                    print("Source device, destination device, source process, destination process, and data required.")
                else:
                    source_device, dest_device = args[0], args[1]
                    source_process, dest_process = args[2], args[3]
                    data = ' '.join(args[4:])
                    sim.send_data_between_processes(source_device, dest_device, source_process, dest_process, data)
            elif choice == 29:
                sim.transport_layer.show_process_table()
            elif choice == 27:
                sim.show_arp_tables()
            elif choice == 19:
                sim.print_routing_tables()
            elif choice == 9:
                if len(args) < 3:
                    print("Sender, receiver, and message required.")
                else:
                    sender, receiver = args[0], args[1]
                    message = ' '.join(args[2:])
                    sim.send_data(sender, receiver, message)
            elif choice == 10:
                if len(args) < 3:
                    print("Sender, hub, and message required.")
                else:
                    sender, hub = args[0], args[1]
                    message = ' '.join(args[2:])
                    sim.hub_broadcast(sender, hub, message)
            elif choice == 13:
                sim.calculate_domains()
                print(f"Broadcast Domains: {sim.broadcast_domains}")
                print(f"Collision Domains: {sim.collision_domains}")
            elif choice == 14:
                sim.show_mac_tables()
            elif choice == 16:
                if len(args) < 1:
                    print("Device name required.")
                else:
                    sim.show_ip_config(args[0])
            elif choice == 17:
                # Clear the network (reset the simulator)
                sim.__init__()
                print("Network cleared.")
            elif choice == 18:
                sim.rip_update_all()
            elif choice == 12:
                sim.show_data_log()
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a valid number as the first argument.")
        except Exception as e:
            print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    main()
    
  

  