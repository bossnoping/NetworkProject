/// ProcessInfo — represents a running process from GET_TOP_PROCS response
class ProcessInfo {
  final int pid;
  final String name;
  final double cpuPercent;
  final double ramPercent;
  final double ramMb;

  ProcessInfo({
    required this.pid,
    required this.name,
    required this.cpuPercent,
    required this.ramPercent,
    required this.ramMb,
  });

  /// Parse a procs list string like:
  ///   {pid:1042,name:chrome.exe,cpu:22%,ram:1.5%}
  static List<ProcessInfo> parseList(String procsStr) {
    final result = <ProcessInfo>[];
    // Extract content between [ and ]
    final bracket = RegExp(r'\[(.*)\]', dotAll: true).firstMatch(procsStr);
    if (bracket == null) return result;

    final content = bracket.group(1)!;
    // Find each {...} block
    final blocks = RegExp(r'\{([^}]+)\}').allMatches(content);

    for (final block in blocks) {
      try {
        final fields = <String, String>{};
        for (final field in block.group(1)!.split(',')) {
          final kv = field.split(':');
          if (kv.length >= 2) {
            fields[kv[0].trim()] = kv.sublist(1).join(':').trim();
          }
        }
        final pid = int.tryParse(fields['pid'] ?? '0') ?? 0;
        final name = fields['name'] ?? 'unknown';
        
        // Skip System Idle Process (PID 0) or idle kernel threads
        if (pid <= 0 || name.toLowerCase().contains('idle')) {
          continue;
        }

        final cpuRaw = double.tryParse(fields['cpu']?.replaceAll('%', '') ?? '0') ?? 0;
        final ramRaw = double.tryParse(fields['ram']?.replaceAll('%', '') ?? '0') ?? 0;
        final ramMbRaw = double.tryParse(fields['ram_mb']?.replaceAll('MB', '') ?? '0') ?? 0;

        result.add(ProcessInfo(
          pid: pid,
          name: name,
          cpuPercent: cpuRaw.clamp(0.0, 100.0),
          ramPercent: ramRaw.clamp(0.0, 100.0),
          ramMb: ramMbRaw,
        ));
      } catch (_) {
        // Skip malformed entries
      }
    }
    return result;
  }
}
