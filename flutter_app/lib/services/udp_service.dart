import 'dart:async';

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

  /// Start listening for UDP broadcasts on port 9000.
  Future<void> start() async {
    try {
      _udp = await UDP.bind(
        Endpoint.any(port: Port(_udpPort)),
      );
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
