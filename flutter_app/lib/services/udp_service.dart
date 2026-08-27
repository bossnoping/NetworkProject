import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:udp/udp.dart';

import '../models/metric_data.dart';

/// UDPService — listens for SRMP METRIC packets broadcast by the Python server.
/// Exposes a stream of [MetricData] for the UI to react to.
class UDPService {
  static const int _udpPort = 9000;

  UDP? _udp;
  final _controller = StreamController<MetricData>.broadcast();

  Stream<MetricData> get stream => _controller.stream;

  bool get isListening => _udp != null;

  /// Send a Wake-on-LAN magic packet to [macAddress].
  static Future<bool> wakeOnLan(
    String macAddress, {
    String broadcastAddress = '255.255.255.255',
  }) async {
    final normalized = macAddress.replaceAll(RegExp(r'[^0-9A-Fa-f]'), '');
    if (normalized.length != 12 ||
        !RegExp(r'^[0-9A-Fa-f]{12}$').hasMatch(normalized)) {
      return false;
    }

    try {
      final mac = List<int>.generate(
        6,
        (index) => int.parse(
          normalized.substring(index * 2, index * 2 + 2),
          radix: 16,
        ),
      );
      final packet = Uint8List.fromList([
        ...List<int>.filled(6, 0xFF),
        ...Iterable<int>.generate(16 * 6, (i) => mac[i % 6]),
      ]);
      final socket = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 0);
      socket.broadcastEnabled = true;
      socket.send(packet, InternetAddress(broadcastAddress), 9);
      socket.send(packet, InternetAddress(broadcastAddress), 7);
      socket.close();
      return true;
    } catch (_) {
      return false;
    }
  }

  /// Start listening for UDP broadcasts on port 9000.
  Future<void> start() async {
    try {
      _udp = await UDP.bind(Endpoint.any(port: Port(_udpPort)));
      // Use the udp 4.0.1 listen API
      _udp!.listen((datagram) {
        if (datagram == null) return;
        final raw = String.fromCharCodes(datagram.data).trim();
        final metric = MetricData.parse(raw);
        if (metric != null) {
          _controller.add(metric);
        }
      });
    } catch (e) {
      _controller.addError('UDP bind failed: $e');
    }
  }

  /// Stop listening.
  Future<void> stop() async {
    _udp?.close();
    _udp = null;
  }

  void dispose() {
    stop();
    _controller.close();
  }
}
