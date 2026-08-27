import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';

import '../models/metric_data.dart';
import '../models/process_info.dart';
import '../services/udp_service.dart';
import '../services/tcp_service.dart';
import 'package:home_widget/home_widget.dart';

/// MonitorProvider — central state manager (ChangeNotifier / Provider).
/// Combines UDP metric data and TCP command/response handling.
class MonitorProvider extends ChangeNotifier {
  final UDPService _udp = UDPService();
  final TCPService _tcp = TCPService();

  // ── State ──────────────────────────────────────────────────────────────────
  MetricData? latestMetric;
  List<ProcessInfo> processes = [];
  List<String> alerts = [];
  List<String> eventLog = [];
  bool isConnected = false;
  bool isLoadingProcs = false;
  String? lastKillResult;
  String? controlResult; // last result shown on Controls page
  String serverHost = '';
  String currentSortby = 'CPU';
  int clientPingMs = -1;
  int currentVolume = -1;
  int currentBrightness = -1;

  // ── Subscriptions ──────────────────────────────────────────────────────────
  StreamSubscription<MetricData>? _udpSub;
  StreamSubscription<bool>? _connSub;
  StreamSubscription<ServerResponse>? _respSub;
  Timer? _procRefreshTimer; // auto-refresh process list every second
  Timer? _clientPingTimer; // client-side ping to 8.8.8.8 every 5s

  // ── Connect ────────────────────────────────────────────────────────────────
  Future<bool> connect(String host) async {
    serverHost = host;
    _log('Connecting to $host...');

    // Start UDP listener
    await _udp.start();
    _udpSub = _udp.stream.listen((metric) async {
      latestMetric = metric;
      notifyListeners();

      // Update Home Widget (Android / iOS only — not supported on desktop)
      if (Platform.isAndroid || Platform.isIOS) {
        try {
          await HomeWidget.saveWidgetData<String>(
            'cpu',
            '${metric.cpu.toStringAsFixed(1)}%',
          );
          await HomeWidget.saveWidgetData<String>(
            'ram',
            '${metric.ram.toStringAsFixed(1)}%',
          );
          await HomeWidget.saveWidgetData<String>(
            'disk',
            '${metric.disk.toStringAsFixed(1)}%',
          );
          await HomeWidget.saveWidgetData<String>(
            'temp',
            '${metric.tempCpu.toStringAsFixed(1)}°C',
          );
          await HomeWidget.saveWidgetData<String>(
            'status',
            isConnected ? 'ONLINE' : 'OFFLINE',
          );
          await HomeWidget.updateWidget(
            androidName: 'AppWidgetProvider',
            // iOSName: 'SrmpWidget', // Un-comment if iOS is supported
          );
        } catch (e) {
          _log('Widget update failed: $e');
        }
      }
    });

    // TCP connection
    final ok = await _tcp.connect(host);
    if (!ok) {
      _log('TCP connection failed');
      return false;
    }

    isConnected = true;
    if (Platform.isAndroid || Platform.isIOS) {
      await HomeWidget.saveWidgetData<String>('server_host', host);
      await HomeWidget.saveWidgetData<String>('status', 'ONLINE');
      await HomeWidget.updateWidget(androidName: 'AppWidgetProvider');
    }
    _log('Connected to $host');
    notifyListeners();

    // Listen for TCP connection state changes
    _connSub = _tcp.connectionState.listen((connected) {
      isConnected = connected;
      if (!connected) _log('Disconnected from server');
      notifyListeners();
    });

    // Listen for TCP push events (202 alerts, kill responses, etc.)
    _respSub = _tcp.responses.listen((resp) {
      if (resp.isAlert) {
        alerts.insert(0, resp.body);
        if (alerts.length > 5) alerts.removeLast();
        _log('⚠️  ALERT: ${resp.body}');
      } else if (resp.isOk && resp.body.contains('PROC_KILLED')) {
        lastKillResult = '✅ ${resp.body}';
        _log('${resp.statusCode} ${resp.phrase} - ${resp.body}');
      } else if (resp.isOk && resp.body.contains('SYSTEM_')) {
        controlResult = '✅ ${resp.body}';
        _log('🔌 ${resp.body}');
      } else if (resp.isOk &&
          (resp.body.startsWith('VOLUME_SET_') ||
              resp.body.startsWith('BRIGHTNESS_SET_'))) {
        controlResult = '✅ ${resp.body}';
      } else if (resp.isError) {
        final body = resp.body;
        final isControlError =
            body.contains('BRIGHTNESS') ||
            body.contains('VOLUME') ||
            body.contains('SYSTEM') ||
            body.contains('LOCK');
        if (isControlError) {
          controlResult = '❌ $body';
        } else {
          lastKillResult = '❌ ${resp.phrase}: $body';
          _log('${resp.statusCode} ${resp.phrase} - $body');
        }
      }
      notifyListeners();
    });

    // Initial process load
    await refreshProcesses();

    // ── Fetch initial system settings ──────────────────────────────────
    _fetchSystemSettings();

    // ── Start auto-refresh timer (every second) ───────────────────────────
    _procRefreshTimer = Timer.periodic(
      const Duration(seconds: 1),
      (_) => _silentRefreshProcesses(),
    );

    // ── Start client-side ping timer (every 5 seconds) ───────────────────
    _measureClientPing(); // first measurement immediately
    _clientPingTimer = Timer.periodic(
      const Duration(seconds: 5),
      (_) => _measureClientPing(),
    );

    return true;
  }

  // ── Disconnect ─────────────────────────────────────────────────────────────
  Future<void> disconnect() async {
    _procRefreshTimer?.cancel();
    _procRefreshTimer = null;
    _clientPingTimer?.cancel();
    _clientPingTimer = null;
    await _udpSub?.cancel();
    await _connSub?.cancel();
    await _respSub?.cancel();
    await _udp.stop();
    await _tcp.disconnect();
    isConnected = false;
    if (Platform.isAndroid || Platform.isIOS) {
      await HomeWidget.saveWidgetData<String>('status', 'OFFLINE');
      await HomeWidget.updateWidget(androidName: 'AppWidgetProvider');
    }
    latestMetric = null;
    processes = [];
    alerts = [];
    clientPingMs = -1;
    currentVolume = -1;
    currentBrightness = -1;
    controlResult = null;
    notifyListeners();
  }

  // ── Process Management ─────────────────────────────────────────────────────
  Future<void> refreshProcesses({String sortby = 'CPU'}) async {
    if (!isConnected) return;
    currentSortby = sortby; // remember for auto-refresh
    isLoadingProcs = true;
    notifyListeners();

    processes = await _tcp.getTopProcesses(limit: 8, sortby: sortby);
    isLoadingProcs = false;
    _log('Loaded ${processes.length} processes (sort: $sortby)');
    notifyListeners();
  }

  /// Silent refresh — used by timer, no loading spinner, no log spam
  Future<void> _silentRefreshProcesses() async {
    if (!isConnected) return;
    final updated = await _tcp.getTopProcesses(limit: 8, sortby: currentSortby);
    if (updated.isNotEmpty) {
      processes = updated;
      notifyListeners();
    }
  }

  void killProcess(int pid, String name) {
    _tcp.killProcess(pid);
    _log('KILL_PROC pid=$pid sent');
    // Refresh list after a short delay
    Future.delayed(
      const Duration(milliseconds: 800),
      () => refreshProcesses(sortby: currentSortby),
    );
  }

  void dismissAlert(int index) {
    if (index < alerts.length) {
      alerts.removeAt(index);
      notifyListeners();
    }
  }

  // ── System Control ───────────────────────────────────────────────────────────────
  void setVolume(int level) {
    _tcp.setVolume(level);
    currentVolume = level;
    if (Platform.isAndroid || Platform.isIOS) {
      unawaited(HomeWidget.saveWidgetData<String>('volume', '$level'));
    }
    controlResult = null; // clear while waiting for response
    notifyListeners();
  }

  void setBrightness(int level) {
    _tcp.setBrightness(level);
    currentBrightness = level;
    if (Platform.isAndroid || Platform.isIOS) {
      unawaited(HomeWidget.saveWidgetData<String>('brightness', '$level'));
    }
    controlResult = null;
    notifyListeners();
  }

  void sysPower(String action) {
    _tcp.sysPower(action);
    controlResult = null;
    _log('SYS_POWER action=$action sent');
  }

  Future<bool> wakePc(String macAddress) async {
    final sent = await UDPService.wakeOnLan(macAddress);
    controlResult = sent
        ? '✅ Wake-on-LAN packet sent'
        : '❌ Invalid MAC address or packet could not be sent';
    _log(sent ? 'Wake-on-LAN sent to $macAddress' : 'Wake-on-LAN failed');
    notifyListeners();
    return sent;
  }

  void clearControlResult() {
    controlResult = null;
    notifyListeners();
  }

  Future<void> _fetchSystemSettings() async {
    if (!isConnected) return;
    final vol = await _tcp.getSetting('volume');
    if (vol >= 0) {
      currentVolume = vol;
      notifyListeners();
    }
    final bright = await _tcp.getSetting('brightness');
    if (bright >= 0) {
      currentBrightness = bright;
      notifyListeners();
    }
  }

  // ── Client Ping ────────────────────────────────────────────────────────────
  Future<void> _measureClientPing() async {
    try {
      final stopwatch = Stopwatch()..start();
      final socket = await Socket.connect(
        '8.8.8.8',
        53,
        timeout: const Duration(seconds: 3),
      );
      stopwatch.stop();
      socket.destroy();
      clientPingMs = stopwatch.elapsedMilliseconds;
    } catch (_) {
      clientPingMs = -1;
    }
    notifyListeners();
  }

  // ── Internal ───────────────────────────────────────────────────────────────
  void _log(String msg) {
    final ts = DateTime.now();
    final stamp =
        '${ts.hour.toString().padLeft(2, '0')}:${ts.minute.toString().padLeft(2, '0')}:${ts.second.toString().padLeft(2, '0')}';
    eventLog.insert(0, '[$stamp] $msg');
    if (eventLog.length > 50) eventLog.removeLast();
  }

  @override
  void dispose() {
    _procRefreshTimer?.cancel();
    _clientPingTimer?.cancel();
    _udpSub?.cancel();
    _connSub?.cancel();
    _respSub?.cancel();
    _udp.dispose();
    _tcp.dispose();
    super.dispose();
  }
}
