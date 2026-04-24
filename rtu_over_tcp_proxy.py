import argparse
import socket
import struct
import threading


def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def validate_crc(frame):
    if len(frame) < 4:
        return False
    crc_calc = crc16(frame[:-2])
    crc_recv = frame[-2] | (frame[-1] << 8)
    return crc_calc == crc_recv


def rtu_frame_length(buf):
    if len(buf) < 2:
        return None
    func = buf[1]
    if func in (1, 2, 3, 4, 5, 6):
        expected = 8
    elif func in (15, 16):
        if len(buf) < 7:
            return None
        byte_count = buf[6]
        expected = 9 + byte_count
    elif func == 23:
        if len(buf) < 11:
            return None
        byte_count = buf[10]
        expected = 13 + byte_count
    elif func in (7, 11, 12):
        expected = 4
    else:
        return None

    if len(buf) >= expected:
        return expected
    return None


def recv_exact(sock, n):
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise IOError("Connection closed")
        data.extend(chunk)
    return bytes(data)


def handle_client(conn, addr, target_host, target_port, ignore_crc, verbose):
    if verbose:
        print(f"Client connected from {addr[0]}:{addr[1]}")
    try:
        target = socket.create_connection((target_host, target_port), timeout=3.0)
        target.settimeout(3.0)
    except Exception as e:
        if verbose:
            print(f"Failed to connect to target {target_host}:{target_port}: {e}")
        conn.close()
        return

    conn.settimeout(1.0)
    buffer = b""
    tx_id = 0

    try:
        while True:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                buffer += data
            except socket.timeout:
                data = b""
            except Exception:
                break

            while True:
                frame_len = rtu_frame_length(buffer)
                if frame_len is None:
                    break

                frame = buffer[:frame_len]
                buffer = buffer[frame_len:]

                if not ignore_crc and not validate_crc(frame):
                    if verbose:
                        print("Dropped frame with bad CRC")
                    continue

                unit = frame[0]
                pdu = frame[1:-2]

                tx_id = (tx_id + 1) & 0xFFFF
                mbap = struct.pack(">HHH", tx_id, 0, len(pdu) + 1) + bytes([unit]) + pdu

                target.sendall(mbap)

                rsp_header = recv_exact(target, 7)
                length = struct.unpack(">H", rsp_header[4:6])[0]
                unit_rsp = rsp_header[6]
                pdu_rsp = recv_exact(target, length - 1)

                rtu_rsp = bytes([unit_rsp]) + pdu_rsp
                crc = crc16(rtu_rsp)
                rtu_rsp += struct.pack("<H", crc)
                conn.sendall(rtu_rsp)
    except Exception as e:
        if verbose:
            print(f"Connection error: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        try:
            target.close()
        except Exception:
            pass
        if verbose:
            print(f"Client disconnected from {addr[0]}:{addr[1]}")


def main():
    parser = argparse.ArgumentParser(description="RTU-over-TCP to Modbus TCP proxy")
    parser.add_argument("--listen-host", default="127.0.0.1", help="Local listen host")
    parser.add_argument("--listen-port", type=int, default=15020, help="Local listen port")
    parser.add_argument("--target-host", default="127.0.0.1", help="Target Modbus TCP host")
    parser.add_argument("--target-port", type=int, default=1502, help="Target Modbus TCP port")
    parser.add_argument("--ignore-crc", action="store_true", help="Ignore bad CRC frames")
    parser.add_argument("--verbose", action="store_true", help="Print connection logs")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.listen_host, args.listen_port))
    sock.listen(5)

    print(f"RTU-over-TCP proxy listening on {args.listen_host}:{args.listen_port}")
    print(f"Forwarding to Modbus TCP at {args.target_host}:{args.target_port}")

    try:
        while True:
            conn, addr = sock.accept()
            t = threading.Thread(
                target=handle_client,
                args=(conn, addr, args.target_host, args.target_port, args.ignore_crc, args.verbose),
                daemon=True,
            )
            t.start()
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()


if __name__ == "__main__":
    main()
