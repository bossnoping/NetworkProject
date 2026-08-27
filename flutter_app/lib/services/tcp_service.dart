import 'dart:async';
import 'dart:io';
import 'dart:convert';
import 'dart:typed_data';

import '../models/process_info.dart';

/// Represents a parsed response from the SRMP TCP server.
class ServerResponse {
  final int statusCode;
  final String phrase;
  final String body;
  final bool isAlert;

  ServerResponse({
    required this.statusCode,
    required this.phrase,
    required this.body,
    required this.isAlert,
  });

  static ServerResponse? parse(String line) {
    final match = RegExp(
      r'^(\d{3}) ([A-Z_ ]+)(?: - (.*))?$',
    ).firstMatch(line.trim());
    if (match == null) return null;
    final code = int.tryParse(match.group(1)!) ?? 0;
    return ServerResponse(
      statusCode: code,
      phrase: match.group(2)!.trim(),
      body: match.group(3) ?? '',
      isAlert: code == 202,
    );
  }

  bool get isOk => statusCode == 200;
  bool get isError => statusCode >= 400;
}

/// TCPService — maintains a persistent TCP connection to the SRMP server.
/// Provides methods to send commands and exposes a stream of [ServerResponse].
class TCPService {
  static const int _tcpPort = 9001;

  Socket? _socket;
  final _responseController = StreamController<ServerResponse>.broadcast();
  final _connectedController = StreamController<bool>.broadcast();

  Stream<ServerResponse> get responses => _responseController.stream;
  Stream<bool> get connectionState => _connectedController.stream;

  bool _connected = false;
  bool get isConnected => _connected;

  String _buffer = '';

  /// Connect to SRMP TCP server at [host].
  Future<bool> connect(String host) async {
    try {
      _socket = await Socket.connect(
        host,
        _tcpPort,
        timeout: const Duration(seconds: 10),
      );
      _connected = true;
      _connectedController.add(true);

      // Listen for incoming data (responses + push events)
      _socket!.listen(
        (Uint8List data) {
          try {
            _buffer += utf8.decode(data, allowMalformed: true);
            while (_buffer.contains('\n')) {
              final nl = _buffer.indexOf('\n');
              final line = _buffer.substring(0, nl).trim();
              _buffer = _buffer.substring(nl + 1);
              if (line.isEmpty) continue;
              final resp = ServerResponse.parse(line);
              if (resp != null) _responseController.add(resp);
            }
          } catch (e) {
            print('Socket onData error: $e');
            // Do not disconnect, just drop malformed data
          }
        },
        onError: (e) {
          _handleDisconnect();
        },
        onDone: () {
          _handleDisconnect();
        },
      );
      return true;
    } catch (e) {
      _connected = false;
      _connectedController.add(false);
      return false;
    }
  }

  void _handleDisconnect() {
    _connected = false;
    _connectedController.add(false);
    _socket = null;
  }

  /// Send a raw SRMP command string (newline appended automatically).
  void sendCommand(String command) {
    if (!_connected || _socket == null) return;
    _socket!.add(utf8.encode('$command\n'));
  }

  // Mutex: prevent overlapping GET_TOP_PROCS requests (auto-refresh + manual)
  bool _fetchingProcs = false;

  /// Request top processes sorted by [sortby] ('CPU' or 'RAM').
  Future<List<ProcessInfo>> getTopProcesses({
    int limit = 8,
    String sortby = 'CPU',
  }) async {
    // Skip if a request is already in flight
    if (_fetchingProcs) return [];
    _fetchingProcs = true;

    try {
      // Use a Completer so only THIS call captures the next procs= response
      final completer = Completer<List<ProcessInfo>>();
      late StreamSubscription<ServerResponse> sub;
      sub = responses.listen((r) {
        if (r.body.contains('procs=') && !completer.isCompleted) {
          completer.complete(ProcessInfo.parseList(r.body));
          sub.cancel();
        }
      });

      // Subscribe before sending because the server may respond immediately.
      sendCommand('GET_TOP_PROCS limit=$limit sortby=$sortby');

      final result = await completer.future.timeout(
        const Duration(seconds: 5),
        onTimeout: () {
          sub.cancel();
          return [];
        },
      );
      return result;
    } catch (_) {
      return [];
    } finally {
      _fetchingProcs = false;
    }
  }

  /// Send a KILL_PROC command for a process id.
  void killProcess(int pid) {
    sendCommand('KILL_PROC pid=$pid');
  }

  /// Set master volume (0–100).
  void setVolume(int level) {
    sendCommand('SET_VOL level=$level');
  }

  /// Set screen brightness (0–100). Works on laptops with built-in displays.
  void setBrightness(int level) {
    sendCommand('SET_BRIGHTNESS level=$level');
  }

  /// Send a power control command: LOCK, SHUTDOWN, or RESTART.
  void sysPower(String action) {
    sendCommand('SYS_POWER action=$action');
  }

  /// Get a system setting by name ('volume' or 'brightness').
  /// Returns the integer value, or -1 on failure/timeout.
  Future<int> getSetting(String name) async {
    final completer = Completer<int>();
    late StreamSubscription<ServerResponse> sub;
    sub = responses.listen((r) {
      if (r.body.contains('SETTING_VALUE') &&
          r.body.contains('name=$name') &&
          !completer.isCompleted) {
        final m = RegExp(r'value=(\d+)').firstMatch(r.body);
        completer.complete(m != null ? int.tryParse(m.group(1)!) ?? -1 : -1);
        sub.cancel();
      } else if (r.isError && !completer.isCompleted) {
        completer.complete(-1);
        sub.cancel();
      }
    });

    // Subscribe before sending because the server may respond immediately.
    sendCommand('GET_SETTING name=$name');

    return completer.future.timeout(
      const Duration(seconds: 5),
      onTimeout: () {
        sub.cancel();
        return -1;
      },
    );
  }

  /// Set a system setting by name.
  void setSetting(String name, int value) {
    sendCommand('SET_SETTING name=$name value=$value');
  }

  /// Disconnect from server.
  Future<void> disconnect() async {
    await _socket?.close();
    _socket = null;
    _connected = false;
    _connectedController.add(false);
  }

  void dispose() {
    disconnect();
    _responseController.close();
    _connectedController.close();
  }
}
