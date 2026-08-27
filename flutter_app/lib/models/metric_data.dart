/// MetricData — parsed from a SRMP UDP METRIC packet
class MetricData {
  final double cpu;
  final double ram;
  final double disk;
  final double tempCpu;
  final double tempGpu;
  final double netUp;
  final double netDown;
  final bool netOnline;
  final int netPing;
  final int uptime;
  final DateTime receivedAt;

  MetricData({
    required this.cpu,
    required this.ram,
    required this.disk,
    required this.tempCpu,
    required this.tempGpu,
    required this.netUp,
    required this.netDown,
    required this.netOnline,
    required this.netPing,
    required this.uptime,
    DateTime? receivedAt,
  }) : receivedAt = receivedAt ?? DateTime.now();

  /// Parse a METRIC packet string into a MetricData object.
  /// Returns null if the packet is malformed.
  static MetricData? parse(String packet) {
    try {
      if (!packet.startsWith('METRIC ')) return null;
      final parts = packet.substring(7).split(' ');
      final map = <String, String>{};
      for (final p in parts) {
        final idx = p.indexOf('=');
        if (idx < 0) continue;
        map[p.substring(0, idx)] = p.substring(idx + 1);
      }

      double parseDouble(String key, String suffix) {
        if (!map.containsKey(key)) return 0.0;
        return double.tryParse(map[key]!.replaceAll(suffix, '')) ?? 0.0;
      }

      int parseInt(String key, String suffix) {
        if (!map.containsKey(key)) return 0;
        return int.tryParse(map[key]!.replaceAll(suffix, '')) ?? 0;
      }

      final onlineVal = map['net_online'] ?? '0';
      final isOnline = onlineVal == '1' || onlineVal.toLowerCase() == 'true';

      return MetricData(
        cpu: parseDouble('cpu', '%'),
        ram: parseDouble('ram', '%'),
        disk: parseDouble('disk', '%'),
        tempCpu: parseDouble('temp_cpu', 'C'),
        tempGpu: parseDouble('temp_gpu', 'C'),
        netUp: parseDouble('net_up', 'MB/s'),
        netDown: parseDouble('net_down', 'MB/s'),
        netOnline: isOnline,
        netPing: parseInt('net_ping', 'ms'),
        uptime: parseInt('uptime', 's'),
      );
    } catch (_) {
      return null;
    }
  }

  /// Format uptime as HH:MM:SS
  String get uptimeFormatted {
    final h = uptime ~/ 3600;
    final m = (uptime % 3600) ~/ 60;
    final s = uptime % 60;
    return '${h.toString().padLeft(2, '0')}:'
        '${m.toString().padLeft(2, '0')}:'
        '${s.toString().padLeft(2, '0')}';
  }
}
